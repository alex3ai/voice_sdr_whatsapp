import requests
import json

# URL do seu Bot (ajuste se estiver rodando localmente fora do docker, use localhost)
url = "http://localhost:8000/webhook/evolution"

# --- INSTRUÇÕES DE TESTE ---
# Para que o bot consiga ENVIAR a resposta, o número em 'remoteJid'
# deve ser um número de WhatsApp VÁLIDO e ATIVO, no formato DDI+DDD+Número.
# Exemplo para um número de São Paulo, Brasil: "5511987654321@s.whatsapp.net"
#
# O número que estava nos logs (125743824670857) é inválido e por isso a API falha.
# Substitua o número abaixo pelo seu número pessoal para testar o fluxo completo.

payload = {
    "event": "messages.upsert",
    "data": {
        "key": {
            # IMPORTANTE: Troque pelo seu número de WhatsApp para receber a resposta.
            "remoteJid": "5511999999999@s.whatsapp.net",
            "fromMe": False,
            "id": "TESTE_AUTOMATIZADO_01"
        },
        "messageType": "audioMessage",
        "message": {
            "audioMessage": {
                # O link do áudio pode ser qualquer um, pois a transcrição é simulada.
                "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
                "mimetype": "audio/mp4",
                "seconds": 10
            }
        }
    }
}

print("🚀 Enviando Webhook Simulado...")
print(f"ℹ️  O bot irá responder para o número: {payload['data']['key']['remoteJid'].split('@')[0]}")
print("Certifique-se que este é um número de WhatsApp válido.")

try:
    response = requests.post(url, json=payload, timeout=10)
    print(f"\nStatus Code da sua API: {response.status_code}")
    
    # Tenta imprimir o JSON de resposta, se houver
    try:
        print(f"Resposta da sua API: {response.json()}")
    except json.JSONDecodeError:
        print(f"Resposta da sua API (não-JSON): {response.text}")

except requests.exceptions.RequestException as e:
    print(f"\n❌ Erro ao conectar na sua API: {e}")
    print("Verifique se o seu bot está rodando e acessível na URL:", url)
