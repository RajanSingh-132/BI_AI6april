import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# ---------------------------------------------------------
# NORMALIZE KEYS
# ---------------------------------------------------------
def normalize_keys(row: Dict[str, Any]):
    return {k.strip().lower(): v for k, v in row.items()}


# ---------------------------------------------------------
# AUTO TYPE CONVERSION
# ---------------------------------------------------------
def auto_convert(value):
    try:
        if value is None or str(value).strip() == "":
            return None

        value = str(value).strip()

        if "." in value:
            return float(value)
        return int(value)

    except:
        return value


# ---------------------------------------------------------
# SPLIT NUMERIC / CATEGORICAL
# ---------------------------------------------------------
def split_fields(row: Dict[str, Any]):
    numeric = {}
    categorical = {}

    for k, v in row.items():
        if isinstance(v, (int, float)):
            numeric[k] = v
        else:
            categorical[k] = v

    return numeric, categorical


# ---------------------------------------------------------
# CREATE HUMAN FRIENDLY TEXT (FOR EMBEDDING)
# ---------------------------------------------------------
def create_semantic_text(row: Dict[str, Any]):

    if "month" in row:
        base = f"For {row['month']}, "
    else:
        base = "Data point: "

    parts = []

    for k, v in row.items():
        if k != "month":
            parts.append(f"{k.replace('_', ' ')} is {v}")

    return base + ", ".join(parts) + "."


# ---------------------------------------------------------
# MAIN FUNCTION (UPDATED FOR JSON INPUT)
# ---------------------------------------------------------
def process_dataset(
    data: List[Dict[str, Any]],
    file_name: str,
    embedding_client,
    mongo_client
):

    try:
        logger.info(f"[PROCESS] Processing dataset: {file_name}")

        documents = []

        for idx, raw_row in enumerate(data):

            try:
                # ✅ Normalize keys
                row = normalize_keys(raw_row)

                structured_data = {}

                # ✅ Clean + convert values
                for k, v in row.items():
                    key = k.strip().lower()

                    if not key:
                        continue

                    converted_value = auto_convert(v)

                    if converted_value is None:
                        continue

                    structured_data[key] = converted_value

                if not structured_data:
                    continue

                # ✅ Split fields
                numeric_fields, categorical_fields = split_fields(structured_data)

                # ✅ Create semantic text
                content = create_semantic_text(structured_data)

                # ✅ Generate embedding
                embedding = embedding_client.generate_embedding(content)

                if not embedding:
                    logger.warning(f"[SKIP] Embedding failed at row {idx}")
                    continue

                # ✅ FINAL DOCUMENT (FOR MONGODB)
                document = {
                    "type": "embedding",   # 🔥 IMPORTANT
                    "file_name": file_name,

                    "data": structured_data,
                    "content": content,

                    "metadata": {
                        "numeric": numeric_fields,
                        "categorical": categorical_fields
                    },

                    "embedding": embedding
                }

                documents.append(document)

            except Exception as e:
                logger.error(f"[ROW_ERR] Row {idx} failed: {e}")
                continue

        # ✅ Store in MongoDB
        if documents:
            mongo_client.insert_documents(documents)
            logger.info(f"✅ {len(documents)} embeddings stored")

    except Exception as e:
        logger.error(f"[PROCESS_ERR] {e}")