import requests

url = "http://127.0.0.1:8000/api/v1/auth/login/"

payload = {
    "email": "teste@email.com",
    "password": "Senha@1234"
}

headers = {
    "Content-Type": "application/json"
}

try:
    response = requests.post(url, json=payload, headers=headers)

    print("Status Code:", response.status_code)

    # Tenta converter resposta para JSON
    try:
        print("Resposta JSON:")
        print(response.json())
    except:
        print("Resposta (texto bruto):")
        print(response.text)

except requests.exceptions.RequestException as e:
    print("Erro ao fazer requisição:", e)