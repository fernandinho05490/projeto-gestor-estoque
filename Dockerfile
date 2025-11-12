# --- Fase 1: A Imagem Base (O "Molde" com GPU) ---
FROM nvidia/cuda:12.1.0-devel-ubuntu22.04

# Define uma variável de ambiente para que os logs do Python saiam direto
ENV PYTHONUNBUFFERED=1

# --- Fase 2: Instalar o Python e o CONECTOR OPENCL BÁSICO ---
RUN apt-get update && \
    apt-get install -y \
    python3.11 \
    python3.11-venv \
    curl \
    # --- OPENCL BÁSICO (SEM DRIVER ESPECÍFICO) ---
    ocl-icd-libopencl1 \
    opencl-headers \
    clinfo \
    && \
    # 3. Instalar o Python e o Pip
    ln -sf /usr/bin/python3.11 /usr/bin/python && \
    curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py && \
    python /tmp/get-pip.py && \
    rm /tmp/get-pip.py

# --- O DRIVER OPENCL JÁ VEM COM A IMAGEM CUDA ---
# --- VERIFICAÇÃO SIMPLES ---
RUN clinfo || echo "OpenCL não disponível ainda, mas continuando..."

# --- Fase 3: Instalar as Bibliotecas do Python (requirements) ---
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# --- Fase 4: Copiar o Código da Nossa Aplicação ---
COPY . .