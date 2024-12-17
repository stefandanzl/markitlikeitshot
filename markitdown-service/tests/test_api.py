from .conftest import TEST_WIKI_URL, TEST_BBC_URL, TEST_HTML

def test_convert_text_basic(client):
    """Test basic text conversion"""
    response = client.post(
        "/convert/text",
        json={"content": TEST_HTML}
    )
    assert response.status_code == 200
    assert "# Hello World" in response.text
    assert "This is a test" in response.text

def test_convert_wikipedia_url(client):
    """Test Wikipedia URL conversion with specific content checks"""
    response = client.post(
        "/convert/url",
        json={"url": TEST_WIKI_URL}
    )
    
    assert response.status_code == 200
    content = response.text
    
    # Test for key sections that should be present
    assert "# Goat" in content
    assert "Domesticated mammal" in content
    
    # Test for specific content sections
    assert any(section in content for section in ["## Biology", "## Agriculture", "## Uses"])
    
    # Test for proper markdown formatting
    assert content.count('#') >= 2  # Should have multiple heading levels
    assert '|' in content  # Should contain table formatting
    assert '[' in content and ']' in content  # Should contain links

def test_convert_bbc_news_url(client):
    """Test BBC News URL conversion with specific content checks"""
    response = client.post(
        "/convert/url",
        json={"url": TEST_BBC_URL}
    )
    
    assert response.status_code == 200
    content = response.text
    
    # Test for main headline and content
    assert "Snoop Dogg" in content
    assert "Olympics" in content
    assert "Ana Faguy" in content
    assert "BBC News" in content
    
    # Test for proper markdown formatting
    assert content.count('#') >= 1  # Should have at least main heading
    assert '![' in content  # Should contain image markdown
    assert '](' in content  # Should contain links
    
    # Test that main content is present
    assert "There are few people who have become more synonymous with" in content

def test_rate_limiting(fresh_client):
    """Test rate limiting across all endpoints"""
    # Test gradual rate limit
    responses = []
    for _ in range(15):  # Reduced from 120 to 15 (slightly more than our limit of 10)
        response = fresh_client.post(
            "/convert/text",
            json={"content": "<h1>Test</h1>"}
        )
        responses.append(response.status_code)
        if response.status_code == 429:
            break
    
    # Verify we got some successful responses before hitting the limit
    successful_responses = [r for r in responses if r == 200]
    assert len(successful_responses) == 10  # Should get exactly 10 successful responses
    # Verify we eventually hit the rate limit
    assert 429 in responses

def test_rate_limit_headers(fresh_client):
    """Test rate limit headers and enforcement"""
    # First request should succeed and have headers
    response = fresh_client.post(
        "/convert/text",
        json={"content": "<h1>Test</h1>"}
    )
    
    assert response.status_code == 200
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers
    assert "X-RateLimit-Reset" in response.headers

def test_rate_limit_exceeded(rate_limited_client):
    """Test behavior when rate limit is exceeded"""
    response = rate_limited_client.post(
        "/convert/text",
        json={"content": "<h1>Test</h1>"}
    )
    assert response.status_code == 429
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers
    assert "X-RateLimit-Reset" in response.headers
    assert response.headers["X-RateLimit-Remaining"] == "0"

def test_error_handling(client):
    """Test various error scenarios"""
    # Test missing content
    response = client.post("/convert/text", json={})
    assert response.status_code == 422

    # Test invalid JSON
    response = client.post(
        "/convert/text",
        data="invalid json",
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422

    # Test missing file
    response = client.post("/convert/file")
    assert response.status_code == 422

def test_file_size_limit(client):
    """Test file size limit"""
    large_content = b"x" * (11 * 1024 * 1024)  # 11MB (over limit)
    response = client.post(
        "/convert/file",
        files={"file": ("test.txt", large_content, "text/plain")}
    )
    assert response.status_code == 400
    assert "exceeds maximum limit" in response.json()["detail"]

def test_unsupported_file_type(client):
    """Test unsupported file type"""
    content = b"test content"
    response = client.post(
        "/convert/file",
        files={"file": ("test.xyz", content, "application/octet-stream")}
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]

def test_convert_file(client, test_doc_path):
    """Test file conversion"""
    with open(test_doc_path, "rb") as f:
        response = client.post(
            "/convert/file",
            files={"file": ("TestDoc.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        )
    
    assert response.status_code == 200
    content = response.text
    
    # Test for key sections and formatting
    assert "# Skills Summary" in content
    assert "# Education" in content
    assert "# Experience" in content
    assert "## Name of Employer" in content
    assert "### Job Title/Dates of Employment" in content
    
    # Test for some specific content
    assert "Address | Phone Number | Email Address" in content
    assert "FIRST NAME" in content
    assert "Surname" in content
    
    # Verify markdown hierarchy
    assert content.count('#') >= 6  # At least 6 heading markers
    assert "###" in content  # Contains third-level headings