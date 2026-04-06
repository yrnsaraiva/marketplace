import requests

url = "http://127.0.0.1:8000/api/v1/anuncios/criar/"

# ⚠️ Substitua pelo teu token real
access_token = ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzc0Mjk3NjM0LCJpYXQiOjE"
                "3NzQyOTQwMzQsImp0aSI6IjBiNzgyNTk5YzVmMTRhMDNiYzhjMGNhOWRlOWNmZTQwIiwidXNlcl9pZCI6I"
                "jIifQ.Bu0KLcjJhf_tzrMCeU8u5DK8YlU_rDT-BQVFs77qQ64")

payload = {
    "titulo": "iPhone 14 Pro em bom estado",
    "descricao": "Vendo iPhone 14 Pro 256GB, cor preta, sem riscos.",
    "preco": "85000.00",
    "preco_negociavel": True,
    "condicao": "usado",
    "categoria": 17,
    "provincia": "Maputo",
    "cidade": "Maputo",
    "bairro": "Sommerschield"
}

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

try:
    response = requests.post(url, json=payload, headers=headers)

    print("Status Code:", response.status_code)

    try:
        print("Resposta JSON:")
        print(response.json())
    except:
        print("Resposta (texto):")
        print(response.text)

except requests.exceptions.RequestException as e:
    print("Erro:", e)