#!/bin/bash
cd ~/combinationProblemGeneration 
CONFIG_DIR=configs/single-operate
for config in "$CONFIG_DIR"/*.json; do
    nohup uv run main.py --config "$config" >> "logs/$(basename "$config" .json)-$(date +%Y%m%d_%H%M%S).log" 2>&1 &
    echo "Running with config: $config"
done 