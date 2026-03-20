import asyncio
import json
import logging
import re
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.dependencies import DbSession, NovelServiceDep, get_ai_service
from app.constants import TEMPLATE_DIR
from app.models import Book, Chapter
from app.utils.helpers import get_templates
from app.services.agents import ChapterWriterAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/books/{book_id}/chapters", tags=["chapters"])


def extract_chapter_outline(memory_summary: str, chapter_number: int) -> str:
    match = re.search(r"【主线进度】\s*\n(.*?)(?=\n【|$)", memory_summary, re.DOTALL)
    if not match:
        return ""
    outline_text = match.group(1).strip()
    lines = outline_text.split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith(f"第{chapter_number}章") or re.match(rf"^{chapter_number}[:、.]", line):
            parts = re.split(r"[:、.]", line, 1)
            if len(parts) > 1:
                return parts[1].strip()
            return line
    if lines:
        idx = chapter_number - 1
        if idx < len(lines):
            line = lines[idx].strip()
            parts = re.split(r"[:、.]", line, 1)
            if len(parts) > 1:
                return parts[1].strip()
            return line
    return ""


@router.get("/write", response_class=HTMLResponse)
async def write_chapter_form(request: Request, book_id: int, db: DbSession, num: int | None = None, edit: bool = False):
    from app.repositories.novel_repository import NovelRepository

    repo = NovelRepository(db)
    book = repo.get_book_by_id(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")

    max_num = repo.get_max_chapter_number(book_id)
    current = int(book.current_chapter) if book.current_chapter is not None else 0
    next_chapter = max(max_num, current) + 1

    if num is not None:
        chapter_num = num
        if chapter_num < 1:
            raise HTTPException(status_code=400, detail="章节号必须大于0")
        # 禁止跳章节:不允许创建比下一章更靠后的章节
        if chapter_num > next_chapter:
            raise HTTPException(status_code=400, detail=f"请先完成第 {next_chapter} 章,不能跳章创作")
    else:
        chapter_num = next_chapter

    chapter = repo.get_chapter(book_id, chapter_num)

    core_event = (
        chapter.core_event
        if chapter and chapter.core_event
        else extract_chapter_outline(str(book.memory_summary), chapter_num)
    )

    prev_ending = repo.get_prev_ending(book_id, chapter_num)

    is_completed = chapter is not None and chapter.status == "已完成"
    is_editing = is_completed or edit
    existing_content = ""
    if is_editing and chapter:
        existing_content = chapter.content or ""

    templates = get_templates()

    if is_completed and not edit:
        return templates.TemplateResponse(
            request,
            "chapter_preview.html",
            {
                "book": book,
                "chapter_number": chapter_num,
                "chapter": chapter,
                "prev_ending": prev_ending,
                "core_event": core_event,
                "content": existing_content,
            },
        )

    return templates.TemplateResponse(
        request,
        "write_chapter.html",
        {
            "book": book,
            "chapter_number": chapter_num,
            "prev_ending": prev_ending,
            "core_event": core_event,
            "editing": is_editing,
            "chapter": chapter,
            "existing_content": existing_content,
        },
    )


@router.post("/", response_class=HTMLResponse)
async def generate_chapter(
    request: Request,
    book_id: int,
    db: DbSession,
    service: NovelServiceDep,
    chapter_number: int | None = Form(None),
    core_event: str = Form(...),
):
    from app.repositories.novel_repository import NovelRepository

    book = service.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")

    repo = NovelRepository(db)
    max_num = repo.get_max_chapter_number(book_id)
    current = int(book.current_chapter) if book.current_chapter is not None else 0
    next_chapter = max(max_num, current) + 1

    if chapter_number is None:
        chapter_number = next_chapter
    elif chapter_number > next_chapter:
        raise HTTPException(status_code=400, detail=f"请先完成第 {next_chapter} 章,不能跳章创作")

    prev_ending = service.get_prev_ending(book_id, int(chapter_number))

    stream = book.config.get("stream", True)

    templates = get_templates()

    if stream:
        try:
            return templates.TemplateResponse(
                request,
                "partials/edit_chapter.html",
                {
                    "book": book,
                    "chapter_number": chapter_number,
                    "content": "",
                    "stream": True,
                    "core_event": core_event,
                    "prev_ending": prev_ending,
                },
            )
        except TimeoutError:
            logger.error("Timeout during template rendering")
            return HTMLResponse(content="请求超时，请稍后重试", status_code=504)
        except (OSError, ConnectionError) as e:
            logger.error(f"Network error during rendering: {e}")
            return HTMLResponse(content="网络连接失败", status_code=503)
        except Exception as e:
            logger.exception("Unexpected error during template rendering")
            import traceback

            return HTMLResponse(
                content=f"模板渲染失败: {str(e)}<br><pre>{traceback.format_exc()}</pre>", status_code=500
            )
    else:
        from app.utils.config_helper import get_global_config_dict

        global_config = get_global_config_dict(db)
        ai_service = get_ai_service(db)
        agent = ChapterWriterAgent(ai_service, book, global_config)
        try:
            content = await agent.write(int(chapter_number), core_event, prev_ending)
        except TimeoutError:
            logger.error("Timeout during chapter generation")
            return HTMLResponse(content="生成超时，请稍后重试", status_code=504)
        except (OSError, ConnectionError) as e:
            logger.error(f"Network error during chapter generation: {e}")
            return HTMLResponse(content="网络连接失败", status_code=503)
        except Exception as e:
            logger.exception("Error during chapter generation")
            return HTMLResponse(content=f"生成失败: {str(e)}", status_code=500)
        try:
            return templates.TemplateResponse(
                request,
                "partials/edit_chapter.html",
                {
                    "book": book,
                    "chapter_number": chapter_number,
                    "content": content,
                    "stream": False,
                    "core_event": core_event,
                    "prev_ending": prev_ending,
                },
            )
        except TimeoutError:
            logger.error("Timeout during template rendering")
            return HTMLResponse(content="请求超时，请稍后重试", status_code=504)
        except (OSError, ConnectionError) as e:
            logger.error(f"Network error during rendering: {e}")
            return HTMLResponse(content="网络连接失败", status_code=503)
        except Exception as e:
            logger.exception("Unexpected error during template rendering")
            import traceback

            return HTMLResponse(
                content=f"模板渲染失败: {str(e)}<br><pre>{traceback.format_exc()}</pre>", status_code=500
            )


@router.get("/regenerate", response_class=HTMLResponse)
async def regenerate_chapter(request: Request, book_id: int, num: int, db: DbSession, service: NovelServiceDep):
    from app.repositories.novel_repository import NovelRepository

    book = service.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")

    if num < 1:
        raise HTTPException(status_code=400, detail="章节号必须大于0")

    repo = NovelRepository(db)
    max_num = repo.get_max_chapter_number(book_id)

    # 禁止跳章:只允许重新生成已存在的章节
    if num > max_num:
        raise HTTPException(status_code=400, detail=f"第 {num} 章尚未创建,请先完成第 {max_num} 章")

    chapter = service.get_chapter(book_id, num)

    core_event = (
        chapter.core_event if chapter and chapter.core_event else extract_chapter_outline(str(book.memory_summary), num)
    )

    prev_ending = service.get_prev_ending(book_id, num)

    stream = book.config.get("stream", True)

    templates = get_templates()

    if stream:
        try:
            return templates.TemplateResponse(
                request,
                "partials/edit_chapter.html",
                {
                    "book": book,
                    "chapter_number": num,
                    "content": "",
                    "stream": True,
                    "core_event": core_event,
                    "prev_ending": prev_ending,
                    "regenerate": True,
                },
            )
        except TimeoutError:
            logger.error("Timeout during regenerate template rendering")
            return HTMLResponse(content="请求超时，请稍后重试", status_code=504)
        except (OSError, ConnectionError) as e:
            logger.error(f"Network error during regenerate rendering: {e}")
            return HTMLResponse(content="网络连接失败", status_code=503)
        except Exception as e:
            logger.exception("Unexpected error during regenerate template rendering")
            import traceback

            return HTMLResponse(
                content=f"模板渲染失败: {str(e)}<br><pre>{traceback.format_exc()}</pre>", status_code=500
            )
    else:
        from app.utils.config_helper import get_global_config_dict

        global_config = get_global_config_dict(db)
        ai_service = get_ai_service(db)
        agent = ChapterWriterAgent(ai_service, book, global_config)
        try:
            content = await agent.write(int(num), core_event, prev_ending)
        except TimeoutError:
            logger.error("Timeout during chapter regeneration")
            return HTMLResponse(content="生成超时，请稍后重试", status_code=504)
        except (OSError, ConnectionError) as e:
            logger.error(f"Network error during chapter regeneration: {e}")
            return HTMLResponse(content="网络连接失败", status_code=503)
        except Exception as e:
            logger.exception("Error during chapter regeneration")
            return HTMLResponse(content=f"生成失败: {str(e)}", status_code=500)
        try:
            return templates.TemplateResponse(
                request,
                "partials/edit_chapter.html",
                {
                    "book": book,
                    "chapter_number": num,
                    "content": content,
                    "stream": False,
                    "core_event": core_event,
                    "prev_ending": prev_ending,
                    "regenerate": True,
                },
            )
        except TimeoutError:
            logger.error("Timeout during regenerate template rendering")
            return HTMLResponse(content="请求超时，请稍后重试", status_code=504)
        except (OSError, ConnectionError) as e:
            logger.error(f"Network error during regenerate rendering: {e}")
            return HTMLResponse(content="网络连接失败", status_code=503)
        except Exception as e:
            logger.exception("Unexpected error during regenerate template rendering")
            import traceback

            return HTMLResponse(
                content=f"模板渲染失败: {str(e)}<br><pre>{traceback.format_exc()}</pre>", status_code=500
            )


@router.post("/stream")
async def stream_chapter(
    request: Request,
    book_id: int,
    db: DbSession,
    service: NovelServiceDep,
    chapter_number: int | None = Form(None),
    core_event: str = Form(""),
):
    from app.repositories.novel_repository import NovelRepository

    book = service.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")

    repo = NovelRepository(db)
    max_num = repo.get_max_chapter_number(book_id)
    current = int(book.current_chapter) if book.current_chapter is not None else 0
    next_chapter = max(max_num, current) + 1

    if chapter_number is None:
        chapter_number = next_chapter
    elif chapter_number > next_chapter:
        raise HTTPException(status_code=400, detail=f"请先完成第 {next_chapter} 章,不能跳章创作")

    prev_ending = service.get_prev_ending(book_id, chapter_number)

    ai_service = get_ai_service(db)
    agent = ChapterWriterAgent(ai_service, book, ai_service.global_config)

    async def generate():
        try:
            async for chunk in agent.write_stream(chapter_number, core_event, prev_ending):
                data = json.dumps({"content": chunk}, ensure_ascii=False)
                yield f"{data}\n"
                await asyncio.sleep(0.01)
            yield json.dumps({"done": True}) + "\n"
        except TimeoutError:
            logger.error("Timeout during streaming chapter generation")
            yield json.dumps({"error": "请求超时，请稍后重试"}) + "\n"
        except (OSError, ConnectionError) as e:
            logger.error(f"Network error during streaming: {e}")
            yield json.dumps({"error": "网络连接失败，请检查网络"}) + "\n"
        except Exception as e:
            logger.exception("Error during streaming chapter generation")
            import traceback

            error_msg = f"\n\n--- 生成过程中发生错误 ---\n{str(e)}\n{traceback.format_exc()}\n"
            yield json.dumps({"error": str(e)}) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@router.get("/list", response_class=HTMLResponse)
async def get_chapter_list(book_id: int, db: DbSession, service: NovelServiceDep):
    book = service.get_book(book_id)
    if not book:
        return HTMLResponse(content="书籍不存在", status_code=404)
    chapters = service.get_chapters(book_id)

    templates = get_templates()
    return templates.TemplateResponse("partials/chapter_list.html", {"book": book, "chapters": chapters})


@router.get("/add", response_class=HTMLResponse)
async def add_chapter_form(request: Request, book_id: int, db: DbSession, position: int | None = None):
    from app.repositories.novel_repository import NovelRepository

    repo = NovelRepository(db)
    book = repo.get_book_by_id(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")

    max_num = repo.get_max_chapter_number(book_id)
    if position is None or position < 1:
        position = max_num + 1

    templates = get_templates()
    return templates.TemplateResponse(
        request, "partials/add_chapter.html", {"book": book, "position": position, "max_num": max_num}
    )


@router.post("/add", response_class=HTMLResponse)
async def add_chapter_endpoint(
    request: Request,
    book_id: int,
    db: DbSession,
    service: NovelServiceDep,
    position: int = Form(...),
    title: str = Form(...),
    core_event: str = Form(""),
):
    book = service.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")

    if position < 1:
        return HTMLResponse(content="插入位置必须大于0", status_code=400)

    try:
        chapter = service.add_chapter(book, position, title, core_event)
    except Exception as e:
        logger.exception("Error adding chapter")
        return HTMLResponse(content=f"添加章节失败: {str(e)}", status_code=500)

    templates = get_templates()
    chapters = service.get_chapters(book_id)
    chapter_list_html = templates.get_template("partials/chapter_list.html").render(book=book, chapters=chapters)
    return HTMLResponse(content=chapter_list_html)


@router.post("/save", response_class=HTMLResponse)
async def save_chapter_endpoint(
    request: Request,
    book_id: int,
    db: DbSession,
    service: NovelServiceDep,
    chapter_number: int = Form(...),
    content: str = Form(...),
):
    book = service.get_book(book_id)
    if not book:
        return HTMLResponse(content="书籍不存在", status_code=404)

    if chapter_number < 1:
        return HTMLResponse(content="章节号必须大于0", status_code=400)

    chapter = service.get_chapter(book_id, chapter_number)

    try:
        chapter, _ = service.save_chapter(book, chapter_number, content)
    except TimeoutError:
        logger.error("Timeout during chapter save")
        return HTMLResponse(content="保存超时，请稍后重试", status_code=504)
    except (OSError, ConnectionError) as e:
        logger.error(f"Network error during chapter save: {e}")
        return HTMLResponse(content="网络连接失败", status_code=503)
    except Exception as e:
        logger.exception("Error during chapter save")
        import traceback

        return HTMLResponse(content=f"保存失败: {str(e)}<br><pre>{traceback.format_exc()}</pre>", status_code=500)

    templates = get_templates()
    chapters = service.get_chapters(book_id)
    chapter_list_html = templates.get_template("partials/chapter_list.html").render(book=book, chapters=chapters)
    content_html = templates.get_template("partials/chapter_generated.html").render(
        book=book, chapter=chapter, content=content[:500] + "..."
    )
    oob_html = f'<div id="chapter-list" hx-swap-oob="true">{chapter_list_html}</div>'
    return HTMLResponse(content=oob_html + content_html)


@router.get("/{chapter_num}", response_class=HTMLResponse)
async def read_chapter(request: Request, book_id: int, chapter_num: int, db: DbSession, service: NovelServiceDep):
    book = service.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    chapter = service.get_chapter(book_id, chapter_num)
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")
    content = chapter.content or ""

    templates = get_templates()
    return templates.TemplateResponse(
        request, "chapter_view.html", {"book": book, "chapter": chapter, "content": content}
    )


@router.delete("/{chapter_num}", response_class=HTMLResponse)
async def delete_chapter_endpoint(book_id: int, chapter_num: int, db: DbSession, service: NovelServiceDep):
    book = service.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")

    if chapter_num < 1:
        raise HTTPException(status_code=400, detail="章节号必须大于0")

    success = service.delete_chapter(book, chapter_num)
    if not success:
        raise HTTPException(status_code=404, detail="章节不存在")

    templates = get_templates()
    chapters = service.get_chapters(book_id)
    return HTMLResponse(
        content=templates.get_template("partials/chapter_list.html").render(book=book, chapters=chapters)
    )
