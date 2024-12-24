import pytest
from app.core.validation.validators import (
    validate_file_size,
    validate_file_extension,
    validate_content_type,
    validate_file_content,
    validate_upload_file,
    validate_text_input
)
from app.core.errors.exceptions import FileProcessingError, ContentTypeError
from unittest.mock import AsyncMock, MagicMock

def test_validate_file_size_success():
    """Test file size validation with valid sizes"""
    # Test with content smaller than max size
    content = b"test content"
    max_size = 100
    validate_file_size(content, max_size)  # Should not raise

    # Test with content exactly at max size
    content = b"x" * 100
    max_size = 100
    validate_file_size(content, max_size)  # Should not raise

def test_validate_file_size_failure():
    """Test file size validation with invalid sizes"""
    content = b"test content"
    max_size = 5  # Smaller than content length

    with pytest.raises(FileProcessingError) as exc_info:
        validate_file_size(content, max_size)
    assert "exceeds maximum limit" in str(exc_info.value)

def test_validate_file_extension_success():
    """Test file extension validation with valid extensions"""
    # Test with supported extensions
    allowed_extensions = {'.txt', '.md', '.doc'}
    
    assert validate_file_extension('test.txt', allowed_extensions) == '.txt'
    assert validate_file_extension('test.md', allowed_extensions) == '.md'
    assert validate_file_extension('test.doc', allowed_extensions) == '.doc'
    
    # Test case insensitivity
    assert validate_file_extension('test.TXT', allowed_extensions) == '.txt'
    assert validate_file_extension('test.MD', allowed_extensions) == '.md'

def test_validate_file_extension_failure():
    """Test file extension validation with invalid extensions"""
    allowed_extensions = {'.txt', '.md', '.doc'}

    # Test with unsupported extension
    with pytest.raises(FileProcessingError) as exc_info:
        validate_file_extension('test.pdf', allowed_extensions)
    assert "Unsupported file type" in str(exc_info.value)

    # Test with no extension
    with pytest.raises(FileProcessingError) as exc_info:
        validate_file_extension('test', allowed_extensions)
    assert "No file extension" in str(exc_info.value)

def test_validate_content_type_success():
    """Test content type validation with valid types"""
    # Test with allowed content types
    validate_content_type('text/html')  # Should not raise
    validate_content_type('application/xhtml+xml')  # Should not raise
    
    # Test with content type parameters
    validate_content_type('text/html; charset=utf-8')  # Should not raise
    validate_content_type('application/xhtml+xml; charset=utf-8')  # Should not raise

def test_validate_content_type_failure():
    """Test content type validation with invalid types"""
    # Test with empty content type
    with pytest.raises(ContentTypeError) as exc_info:
        validate_content_type('')
    assert "No content type provided" in str(exc_info.value)

    # Test with unsupported content type
    with pytest.raises(ContentTypeError) as exc_info:
        validate_content_type('application/pdf')
    assert "Unsupported content type" in str(exc_info.value)

def test_validate_file_content_success():
    """Test file content validation with valid content"""
    content = b"test content"
    metadata = {"filename": "test.txt", "content_type": "text/plain"}
    validate_file_content(content, metadata)  # Should not raise

def test_validate_file_content_failure():
    """Test file content validation with invalid content"""
    metadata = {"filename": "test.txt", "content_type": "text/plain"}

    # Test with empty content
    with pytest.raises(FileProcessingError) as exc_info:
        validate_file_content(b"", metadata)
    assert "Empty file provided" in str(exc_info.value)

    # Test with None content
    with pytest.raises(FileProcessingError) as exc_info:
        validate_file_content(None, metadata)
    assert "Empty file provided" in str(exc_info.value)

class MockUploadFile:
    def __init__(self, filename: str, content_type: str, content: bytes):
        self.filename = filename
        self.content_type = content_type
        self._content = content
        self._position = 0

    async def read(self) -> bytes:
        return self._content

    async def seek(self, position: int) -> None:
        self._position = position

@pytest.mark.asyncio
async def test_validate_upload_file_success():
    """Test successful file upload validation"""
    content = b"test content"
    file = MockUploadFile(
        filename="test.txt",
        content_type="text/plain",
        content=content
    )

    ext, returned_content = await validate_upload_file(file=file)
    
    assert ext == '.txt'
    assert returned_content == content

@pytest.mark.asyncio
async def test_validate_upload_file_failure_no_file():
    """Test file upload validation with no file"""
    with pytest.raises(FileProcessingError) as exc_info:
        await validate_upload_file(file=None)
    assert "No file provided" in str(exc_info.value)

@pytest.mark.asyncio
async def test_validate_upload_file_failure_invalid_extension():
    """Test file upload validation with invalid extension"""
    file = MockUploadFile(
        filename="test.invalid",
        content_type="text/plain",
        content=b"test content"
    )

    with pytest.raises(FileProcessingError) as exc_info:
        await validate_upload_file(file=file)
    assert "Unsupported file type" in str(exc_info.value)

@pytest.mark.asyncio
async def test_validate_upload_file_failure_empty_content():
    """Test file upload validation with empty content"""
    file = MockUploadFile(
        filename="test.txt",
        content_type="text/plain",
        content=b""
    )

    with pytest.raises(FileProcessingError) as exc_info:
        await validate_upload_file(file=file)
    assert "Empty file provided" in str(exc_info.value)

@pytest.mark.asyncio
async def test_validate_text_input_success():
    """Test successful text input validation"""
    content = b"test content"
    await validate_text_input(content=content)  # Should not raise

@pytest.mark.asyncio
async def test_validate_text_input_failure_no_content():
    """Test text input validation with no content"""
    with pytest.raises(FileProcessingError) as exc_info:
        await validate_text_input(content=None)
    assert "No content provided" in str(exc_info.value)

@pytest.mark.asyncio
async def test_validate_text_input_failure_empty_content():
    """Test text input validation with empty content"""
    with pytest.raises(FileProcessingError) as exc_info:
        await validate_text_input(content=b"")
    assert "No content provided" in str(exc_info.value)

@pytest.mark.asyncio
async def test_validate_text_input_failure_size_exceeded():
    """Test text input validation with content exceeding size limit"""
    large_content = b"x" * (11 * 1024 * 1024)  # 11MB, exceeds 10MB limit
    
    with pytest.raises(FileProcessingError) as exc_info:
        await validate_text_input(content=large_content)
    assert "exceeds maximum limit" in str(exc_info.value)
