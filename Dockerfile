FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN useradd -m -s /bin/bash stranger
COPY --chown=stranger:stranger . /opt/workspace/
WORKDIR /home/stranger
RUN pip install --no-cache-dir /opt/workspace
RUN kodand --help | head -5
CMD ["bash"]
