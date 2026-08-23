#!/bin/bash
# Starts the local Ollama server used by JOESTAR's offline fallback tier.
# Run this before starting JOESTAR if you want the local-model fallback
# available. Not required otherwise — JOESTAR degrades gracefully without it.
export LD_LIBRARY_PATH="$HOME/.local/ollama/lib/ollama"
export OLLAMA_MODELS="$HOME/.local/ollama/models"
export OLLAMA_HOST="127.0.0.1:11434"
exec ~/.local/ollama/bin/ollama serve
