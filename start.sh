#!/bin/bash

# ========================================
# Script de Inicialização do Voice SDR
# ========================================

set -e  # Para o script se houver qualquer erro

# Cores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "=========================================="
echo "🚀 Iniciando Voice SDR (Evolution API)"
echo "=========================================="
echo ""

# 1. Verifica Dependências
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker não encontrado! Instale antes de continuar.${NC}"
    exit 1
fi

# 2. Setup do .env
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  Arquivo .env não encontrado.${NC}"
    
    if [ -f .env.example ]; then
        echo "   Copiando .env.example para .env..."
        cp .env.example .env
        echo -e "${GREEN}✓ Arquivo .env criado.${NC}"
        echo ""
        echo -e "${YELLOW}🛑 PARE AGORA!${NC}"
        echo "   Você precisa editar o arquivo .env e colocar suas chaves (Gemini/Evolution)."
        echo "   O script vai parar para você fazer isso."
        exit 1
    else
        echo -e "${RED}❌ .env.example não encontrado!${NC}"
        exit 1
    fi
fi

# 3. Validação de Segurança Básica
if grep -q "AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX" .env; then
    echo -e "${RED}❌ ERRO DE CONFIGURAÇÃO:${NC}"
    echo "   Você não alterou a GEMINI_API_KEY no arquivo .env!"
    echo "   Edite o arquivo e tente novamente."
    exit 1
fi

# 4. Preparação de Diretórios (Persistência)
echo "📂 Verificando diretórios de dados..."
mkdir -p evolution_data/instances
mkdir -p evolution_data/store

# 5. Limpeza e Inicialização
echo "♻️  Reiniciando containers..."
docker-compose down 2>/dev/null || true

echo "🔨 Construindo e iniciando..."
docker-compose up -d --build

# 6. Aguarda Healthcheck
echo "⏳ Aguardando serviços (15s)..."
sleep 15

# 7. Relatório Final
echo ""
echo "=========================================="
if docker ps | grep -q voice_sdr_bot; then
    echo -e "${GREEN}✅ SISTEMA ONLINE!${NC}"
    echo ""
    echo "🔗 Conectar WhatsApp: http://localhost:8000/qrcode"
    echo "📊 Dashboard:         http://localhost:8000/"
    echo ""
    echo "📋 Para ver os logs:"
    echo "   docker-compose logs -f sdr-bot"
else
    echo -e "${RED}❌ Falha na inicialização. Verifique os logs:${NC}"
    echo "   docker-compose logs sdr-bot"
fi
echo "=========================================="