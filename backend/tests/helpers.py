def auth(client, email="user@example.com"):
    response = client.post("/api/v1/auth/register", json={"full_name": "Ayesha Khan", "email": email, "password": "secure-pass"})
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}
