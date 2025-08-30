def test_login_csrf_missing_token(client):
    # No CSRF token provided → should be forbidden (403)
    r = client.post("/login", data={"email": "a@b.com", "password": "x"})
    assert r.status_code == 403


def test_login_csrf_valid_token_but_bad_credentials(client):
    # Fetch login form to receive csrftoken cookie
    r_get = client.get("/login")
    assert r_get.status_code == 200
    # Extract token from cookie
    csrftoken = r_get.cookies.get("csrftoken")
    assert csrftoken

    # Submit invalid credentials with correct CSRF token
    r_post = client.post(
        "/login",
        data={"email": "not@exists", "password": "bad", "csrf_token": csrftoken},
    )
    # CSRF passed, but credentials are wrong → 401 Unauthorized
    assert r_post.status_code == 401
