#!/usr/bin/env bash
# Entrena una semilla de un experimento contra un servidor MLflow compartido (varios runs en paralelo).
#   mlflow server --backend-store-uri sqlite:///$PWD/mlflow.db --host 127.0.0.1 --port 5055 &
#   scripts/run_experiment.sh configs/experiments/exp-002.yaml 2
cd "$(dirname "$0")/.."
export MLFLOW_TRACKING_URI=${MLFLOW_TRACKING_URI:-http://127.0.0.1:5055} MLFLOW_REGISTRY_URI=${MLFLOW_REGISTRY_URI:-http://127.0.0.1:5055}
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
mkdir -p logs
name=$(basename "$1" .yaml)-s$2
${PYTHON:-python} pipelines/train.py --config "$1" --seed "$2" > "logs/$name.log" 2>&1
echo "exit $? $name" >> logs/done.txt
