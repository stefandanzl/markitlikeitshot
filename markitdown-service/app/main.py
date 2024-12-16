from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, HttpUrl
from typing import Optional
from markitdown import MarkItDown
from bs4 import BeautifulSoup
import tempfile
import os
import logging
import requests
import re

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(title="MarkItDown API")

# Configure CORS (Consider restricting in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TextInput(BaseModel):
    content: str
    options: Optional[dict] = None

class UrlInput(BaseModel):
    url: HttpUrl
    options: Optional[dict] = None

def clean_html_content(html_content: str) -> str:
    """
    Clean HTML content using BeautifulSoup before conversion to markdown.
    Removes unnecessary elements while preserving important content.
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove definitely unwanted elements
        selectors_to_remove = [
            'script',                    # JavaScript
            'style',                     # CSS
            'iframe',                    # Embedded frames
            '.cookie-notice',            # Cookie notices
            '.newsletter-signup',        # Newsletter signups
            '.advertisement',            # Explicit ads
            '.ads',                      # More ads
            '.social-share',             # Social sharing buttons
            '.comment-section',          # Comment sections
            'form',                      # Forms
            'meta',                      # Meta tags
            'link[rel="stylesheet"]',    # External stylesheets
        ]

        # Navigation elements that are clearly not main content
        nav_selectors = [
            'nav[aria-label="Footer"]',          # Footer navigation
            'nav[aria-label="Primary"]',         # Primary navigation
            'nav.site-header',                   # Site header navigation
            '.global-navigation',                # Global navigation
            '.footer-links',                     # Footer links
            '.skip-link',                        # Skip links
            '.breadcrumbs',                      # Breadcrumb navigation
        ]

        # Remove unwanted elements
        for selector in selectors_to_remove + nav_selectors:
            elements = soup.select(selector)
            for element in elements:
                element.decompose()

        # Remove empty elements (but preserve images and their containers)
        for element in soup.find_all():
            # Skip images and their parent containers
            if element.name == 'img' or element.find('img'):
                continue
            # Skip elements with specific roles
            if element.get('role') in ['main', 'article', 'contentinfo']:
                continue
            # Remove if truly empty
            if len(element.get_text(strip=True)) == 0 and not element.find('img'):
                element.decompose()

        # Convert the cleaned HTML back to string
        cleaned_html = str(soup)
        return cleaned_html

    except Exception as e:
        logger.exception("Error cleaning HTML content")
        return html_content  # Return original content if cleaning fails

def clean_markdown(markdown_text: str) -> str:
    """
    Cleanup of markdown output.
    Handles various formatting issues and improves readability.
    """
    if not markdown_text:
        return ""

    # Initial cleanup
    markdown_text = markdown_text.strip()

    # Fix spacing issues
    markdown_text = re.sub(r'\n{3,}', '\n\n', markdown_text)
    markdown_text = re.sub(r' {3,}', ' ', markdown_text)

    # Fix header formatting
    markdown_text = re.sub(r'(?m)^#+\s*$', '', markdown_text)
    markdown_text = re.sub(r'(?m)^(#+)([^\s])', r'\1 \2', markdown_text)

    # Fix list formatting
    markdown_text = re.sub(r'(?m)^(\s*[-*+])[^\s]', r'\1 ', markdown_text)
    markdown_text = re.sub(r'(?m)^(\s*\d+\.)[^\s]', r'\1 ', markdown_text)

    # Fix table formatting
    def fix_table_row(match):
        cells = [cell.strip() for cell in match.group(0).split('|')]
        return '|' + '|'.join(cells) + '|'

    markdown_text = re.sub(r'\|[^\n]+\|', fix_table_row, markdown_text)

    def fix_table_headers(match):
        header_row = match.group(1)
        cells_count = len([cell for cell in header_row.split('|') if cell.strip()])
        separator = '|' + '|'.join(['---' for _ in range(cells_count)]) + '|'
        return f"{header_row}\n{separator}"

    markdown_text = re.sub(r'(\|[^\n]+\|)\n(?!\|[-|]+\|)', fix_table_headers, markdown_text)

    # Fix inline code formatting
    markdown_text = re.sub(r'(?<!`)`(?!`)([^`]+?)(?<!`)`(?!`)', r'`\1`', markdown_text)

    # Fix blockquote formatting
    markdown_text = re.sub(r'(?m)^>\s*$', '', markdown_text)
    markdown_text = re.sub(r'(?m)^>([^\s])', r'> \1', markdown_text)

    # Fix link formatting
    markdown_text = re.sub(r'\[([^\]]+)\]\s*\(([^\)]+)\)', r'[\1](\2)', markdown_text)

    # Fix emphasis formatting
    markdown_text = re.sub(r'(?<![\*_])\*{2}([^\*]+)\*{2}(?![\*_])', r'**\1**', markdown_text)
    markdown_text = re.sub(r'(?<![\*_])\*([^\*]+)\*(?![\*_])', r'*\1*', markdown_text)

    # Clean up whitespace
    markdown_text = re.sub(r'[ \t]+$', '', markdown_text, flags=re.MULTILINE)
    markdown_text = re.sub(r'^\s+$', '', markdown_text, flags=re.MULTILINE)

    # Ensure proper spacing between different elements
    markdown_text = re.sub(r'\n{3,}', '\n\n', markdown_text)
    markdown_text = re.sub(r'(?m)^(#+.*)\n([^#\n])', r'\1\n\n\2', markdown_text)
    markdown_text = re.sub(r'(?m)(^[^#\n].*)\n(#+)', r'\1\n\n\2', markdown_text)

    return markdown_text.strip()

def save_temp_file(content: bytes, suffix: str) -> str:
    """
    Save content to a temporary file and return the file path.
    """
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        temp_file.write(content)
        temp_file.close()
        logger.debug(f"Temporary file created at: {temp_file.name}")
        return temp_file.name
    except Exception as e:
        logger.exception("Failed to create temporary file")
        raise
    finally:
        temp_file.close()

def process_conversion(file_path: str, ext: str, url: Optional[str] = None, content_type: str = None) -> str:
    """
    Process conversion using MarkItDown and clean the markdown content.
    """
    try:
        converter = MarkItDown()
        
        # Special handling for HTML content that isn't Wikipedia
        if ext.lower() in ['.html', '.htm'] and (not url or "wikipedia.org" not in url):
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            cleaned_html = clean_html_content(html_content)
            # Save cleaned HTML to temporary file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(cleaned_html)

        if url and "wikipedia.org" in url:
            # Use WikipediaConverter for Wikipedia URLs
            logger.debug("Using WikipediaConverter for Wikipedia URL")
            result = converter.convert(file_path, file_extension=ext, url=url, converter_type='wikipedia')
        else:
            result = converter.convert(file_path, file_extension=ext, url=url)
            
        markdown_content = clean_markdown(result.text_content)
        logger.debug("Markdown content cleaned up")
        return markdown_content
    except Exception as e:
        logger.exception("Conversion failed")
        raise

@app.post("/convert/text", response_class=PlainTextResponse)
async def convert_text(text_input: TextInput):
    """Convert text or HTML to markdown."""
    temp_file_path = None
    try:
        logger.debug(f"Received content: {text_input.content[:100]}...")
        content = text_input.content
        
        # If content appears to be HTML, clean it first
        if re.search(r'<[^>]+>', content):
            content = clean_html_content(content)
            
        temp_file_path = save_temp_file(content.encode('utf-8'), suffix='.html')
        markdown_content = process_conversion(temp_file_path, '.html')
        return markdown_content
    except Exception as e:
        logger.exception("Error during text conversion")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
            logger.debug("Temporary file cleaned up")

@app.post("/convert/file", response_class=PlainTextResponse)
async def convert_file(file: UploadFile = File(...)):
    """Convert an uploaded file to markdown."""
    temp_file_path = None
    try:
        supported_extensions = [
            '.pdf', '.docx', '.pptx', '.xlsx', '.wav', '.mp3',
            '.jpg', '.jpeg', '.png', '.html', '.htm', '.txt', '.csv', '.json', '.xml'
        ]
        _, ext = os.path.splitext(file.filename)
        if ext.lower() not in supported_extensions:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unsupported file type: {ext}"
            )
        content = await file.read()
        temp_file_path = save_temp_file(content, suffix=ext)
        markdown_content = process_conversion(temp_file_path, ext)
        return markdown_content
    except HTTPException as he:
        logger.exception("HTTPException during file conversion")
        raise he
    except Exception as e:
        logger.exception("Error during file conversion")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
            logger.debug("Temporary file cleaned up")

@app.post("/convert/url", response_class=PlainTextResponse)
async def convert_url(url_input: UrlInput):
    """Fetch a URL and convert its content to markdown."""
    temp_file_path = None
    try:
        logger.debug(f"Fetching URL: {url_input.url}")
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/91.0.4472.124 Safari/537.36'
            )
        }
        response = requests.get(str(url_input.url), headers=headers, timeout=10)
        response.raise_for_status()

        content = response.content
        if "wikipedia.org" not in str(url_input.url):
            # Only clean non-Wikipedia HTML content
            content = clean_html_content(response.text).encode('utf-8')

        ext = '.html'
        temp_file_path = save_temp_file(content, suffix=ext)
        markdown_content = process_conversion(
            temp_file_path,
            ext,
            url=str(url_input.url)
        )
        return markdown_content
    except requests.RequestException as e:
        logger.exception("Error fetching URL")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error fetching URL: {str(e)}"
        )
    except Exception as e:
        logger.exception("Error during URL conversion")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
            logger.debug("Temporary file cleaned up")