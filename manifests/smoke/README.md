# Runs de prueba del pipeline (smoke tests)

Estos 16 manifiestos son de las primeras ejecuciones de `pipelines/train.py` del
1 de noviembre de 2026: 8 pasos de entrenamiento cada uno y evaluación de un
episodio. Sirvieron para validar el flujo MLflow → manifiesto → DVC. Tres
terminaron con estado `failed`.

No son modelos candidatos, así que el catálogo no los incluye. Se conservan como
evidencia de los intentos, como pide el enunciado. Sus pesos siguen
referenciados en `models/<run_id>.dvc`.
