"""Generate human-readable labels for topic-description JSONL files."""

import argparse
import bz2
import gzip
import json
import logging
import sys
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from impresso_cookbook import get_transport_params  # type: ignore
    from s3_overwrite import add_force_s3_overwrite_argument, assert_can_write_uri
    from smart_open import open as smart_open  # type: ignore
except ModuleNotFoundError:
    get_transport_params = None
    add_force_s3_overwrite_argument = None
    assert_can_write_uri = None
    smart_open = None

try:
    import dotenv
except ModuleNotFoundError:
    dotenv = None


log = logging.getLogger(__name__)

ALLOWED_TOPIC_TYPES = {
    "theme",
    "newspaper_genre",
    "political_news",
    "local_news",
    "international_news",
    "advertisement",
    "obituary",
    "culture_entertainment",
    "sports",
    "religion",
    "legal_administrative",
    "war_military",
    "economy_commerce",
    "literary_narrative",
    "family_everyday_life",
    "ocr_noise",
    "mixed_uncertain",
}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}

TOPIC_LABEL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "labels": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "topic_id": {"type": "string"},
                    "label_short": {"type": "string"},
                    "label_long": {"type": "string"},
                    "topic_type": {
                        "type": "string",
                        "enum": sorted(ALLOWED_TOPIC_TYPES),
                    },
                    "confidence": {
                        "type": "string",
                        "enum": sorted(ALLOWED_CONFIDENCE),
                    },
                    "rationale": {"type": "string"},
                    "representative_terms": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "topic_id",
                    "label_short",
                    "label_long",
                    "topic_type",
                    "confidence",
                    "rationale",
                    "representative_terms",
                ],
            },
        },
        "summary": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "topics_processed": {"type": "integer"},
                "high_confidence": {"type": "integer"},
                "medium_confidence": {"type": "integer"},
                "low_confidence": {"type": "integer"},
                "ocr_noise_topics": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "mixed_uncertain_topics": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "duplicate_labels_resolved": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": [
                "topics_processed",
                "high_confidence",
                "medium_confidence",
                "low_confidence",
                "ocr_noise_topics",
                "mixed_uncertain_topics",
                "duplicate_labels_resolved",
            ],
        },
    },
    "required": ["labels", "summary"],
}


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate conceptual labels for topic-description JSONL files."
    )
    parser.add_argument("--input", required=True, help="Input JSONL, JSONL.GZ, or JSONL.BZ2 file")
    parser.add_argument("--output", required=True, help="Output JSONL, JSONL.GZ, or JSONL.BZ2 file")
    parser.add_argument("--model", default="gpt-5.5", help="OpenAI model to use")
    parser.add_argument("--top-terms", type=int, default=30, help="Top terms per topic to send")
    parser.add_argument(
        "--max-prompt-chars",
        type=int,
        default=120_000,
        help="Approximate maximum prompt size before batching",
    )
    parser.add_argument(
        "--max-topics-per-batch",
        type=int,
        default=0,
        help="Force a maximum number of topics per batch; 0 means automatic",
    )
    parser.add_argument(
        "--mock-response",
        help="Read a structured model response JSON file instead of calling the OpenAI API",
    )
    if add_force_s3_overwrite_argument is not None:
        add_force_s3_overwrite_argument(parser)
    else:
        parser.add_argument(
            "--force-s3-overwrite",
            default=False,
            help="Allow overwriting existing s3:// outputs. Requires project S3 dependencies.",
        )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )
    return parser.parse_args(argv)


def open_text(path: str, mode: str = "rt"):
    if path.startswith("s3://"):
        if smart_open is None or get_transport_params is None:
            raise RuntimeError(
                "S3 input/output requires smart_open and the cookbook Python helpers"
            )
        return smart_open(
            path,
            mode,
            encoding="utf-8",
            transport_params=get_transport_params(path),
        )
    if path.endswith(".bz2"):
        return bz2.open(path, mode, encoding="utf-8")
    if path.endswith(".gz"):
        return gzip.open(path, mode, encoding="utf-8")
    return open(path, mode, encoding="utf-8")


def topic_id_for(record: Dict[str, Any]) -> str:
    if record.get("id") is not None:
        return str(record["id"])
    if record.get("topic_id") is not None:
        return str(record["topic_id"])
    if record.get("topic") is not None:
        return str(record["topic"])
    raise ValueError(f"Cannot infer topic id from record: {record}")


def topic_terms(record: Dict[str, Any], top_terms: int) -> List[str]:
    word_probs = record.get("word_probs") or []
    terms = []
    for item in word_probs[:top_terms]:
        if isinstance(item, dict) and item.get("word"):
            terms.append(str(item["word"]))
        elif isinstance(item, str):
            terms.append(item)
    return terms


def read_topics(path: str, top_terms: int) -> List[Dict[str, Any]]:
    topics = []
    with open_text(path) as input_file:
        for line_number, line in enumerate(input_file, 1):
            if not line.strip():
                continue
            record = json.loads(line)
            topic_id = topic_id_for(record)
            terms = topic_terms(record, top_terms)
            if not terms:
                raise ValueError(f"Topic {topic_id} on line {line_number} has no terms")
            topics.append(
                {
                    "topic_id": topic_id,
                    "topic": record.get("topic"),
                    "language": record.get("lg"),
                    "topic_model": record.get("topic_model"),
                    "top_terms": terms,
                }
            )
    if not topics:
        raise ValueError(f"No topic records found in {path}")
    return topics


def build_prompt(topics: List[Dict[str, Any]], assigned_labels: List[Dict[str, str]]) -> str:
    payload = {
        "task": "label_one_language_topic_model",
        "topics": topics,
        "already_assigned_labels": assigned_labels,
    }
    return (
        "You are given one topic-description JSONL file for an LDA topic model "
        "trained on historical newspaper text.\n\n"
        "Task:\n"
        "Generate short, meaningful conceptual labels for every topic in the input.\n\n"
        "Context:\n"
        "- The topic model was trained on nouns and proper nouns extracted from historical newspapers.\n"
        "- Topics may represent themes, newspaper genres, registers, named-entity clusters, OCR noise, or diachronic language layers.\n"
        "- Do not assume that topic numbers are comparable across languages or models.\n"
        "- Interpret each topic from its top words and metadata only.\n"
        "- Some topics may be semantically coherent; others may be OCR/noise or formulaic genre topics.\n\n"
        "Labeling rules:\n"
        "1. Prefer conceptual labels over keyword strings.\n"
        "2. Keep labels short and reusable. Use noun phrases, not full sentences.\n"
        "3. If a topic is mostly broken OCR fragments, spelling debris, or malformed tokens, label it as OCR/noise.\n"
        "4. If a topic captures a recurring newspaper format rather than a semantic theme, label the genre.\n"
        "5. If a topic is diachronic/register-specific, mention that.\n"
        "6. If a topic mixes several domains, choose the most plausible dominant interpretation and set confidence to medium or low.\n"
        "7. Avoid over-specific labels based only on one or two named entities unless the whole topic clearly supports it.\n"
        "8. Preserve all topic_id values exactly.\n"
        "9. Make labels mutually distinct across the whole language model and avoid duplicates from already_assigned_labels.\n"
        "10. Do not invent information not supported by the topic words.\n\n"
        "Few-shot example 1:\n"
        "Topic words: bey, könig, nachricht, frankreich, stadt, tag, truppe, mann, general, armee, minister, kaiser, land, schiff, brief, paris, befehl\n"
        "Output label: Eighteenth-century political news; topic_type political_news; confidence high.\n\n"
        "Few-shot example 2:\n"
        "Topic words: ver, mil, dle, stch, ste, ben, der, che, ter, nnd, oon\n"
        "Output label: OCR fragments; topic_type ocr_noise; confidence high.\n\n"
        "Important: The goal is not to produce perfect historical interpretation. "
        "The goal is to create stable, human-readable labels useful for browsing topic "
        "assignments in a newspaper interface. Prefer cautious, transparent labels over "
        "clever but unsupported ones.\n\n"
        "Return JSON matching the requested schema. Input follows:\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


def make_batches(topics: List[Dict[str, Any]], max_prompt_chars: int, max_topics_per_batch: int) -> List[List[Dict[str, Any]]]:
    if max_topics_per_batch > 0:
        return [
            topics[i : i + max_topics_per_batch]
            for i in range(0, len(topics), max_topics_per_batch)
        ]
    batches: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []
    for topic in topics:
        candidate = current + [topic]
        if current and len(build_prompt(candidate, [])) > max_prompt_chars:
            batches.append(current)
            current = [topic]
        else:
            current = candidate
    if current:
        batches.append(current)
    return batches


def extract_response_json(response: Any) -> Dict[str, Any]:
    if hasattr(response, "output_text"):
        return json.loads(response.output_text)
    if isinstance(response, dict):
        return response
    return json.loads(str(response))


def call_openai(prompt: str, model: str) -> Dict[str, Any]:
    try:
        from openai import OpenAI
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The OpenAI Python package is required. Install it with `pip install openai`."
        ) from exc

    client = OpenAI()
    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "You label historical newspaper topic models. "
                    "Return only valid structured JSON."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "topic_label_batch",
                "strict": True,
                "schema": TOPIC_LABEL_SCHEMA,
            }
        },
    )
    return extract_response_json(response)


def validate_labels(response: Dict[str, Any], topics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(response, dict):
        raise ValueError("Model response is not a JSON object")
    labels = response.get("labels")
    if not isinstance(labels, list):
        raise ValueError("Model response has no labels array")
    expected_ids = [topic["topic_id"] for topic in topics]
    observed_ids = [label.get("topic_id") for label in labels]
    if Counter(observed_ids) != Counter(expected_ids):
        raise ValueError(
            "Output topic_id set does not match input topic_id set: "
            f"expected {expected_ids}, observed {observed_ids}"
        )

    topic_terms_by_id = {topic["topic_id"]: set(topic["top_terms"]) for topic in topics}
    validated = []
    for label in labels:
        topic_id = label["topic_id"]
        for field in [
            "label_short",
            "label_long",
            "topic_type",
            "confidence",
            "rationale",
            "representative_terms",
        ]:
            if field not in label:
                raise ValueError(f"{topic_id} is missing required field {field}")
        if label["topic_type"] not in ALLOWED_TOPIC_TYPES:
            raise ValueError(f"{topic_id} has invalid topic_type {label['topic_type']}")
        if label["confidence"] not in ALLOWED_CONFIDENCE:
            raise ValueError(f"{topic_id} has invalid confidence {label['confidence']}")
        terms = label["representative_terms"]
        if not isinstance(terms, list) or not 5 <= len(terms) <= 10:
            raise ValueError(f"{topic_id} representative_terms must contain 5-10 terms")
        invalid_terms = [term for term in terms if term not in topic_terms_by_id[topic_id]]
        if invalid_terms:
            raise ValueError(
                f"{topic_id} representative_terms not copied from topic words: {invalid_terms}"
            )
        validated.append(
            {
                "topic_id": topic_id,
                "label_short": label["label_short"],
                "label_long": label["label_long"],
                "topic_type": label["topic_type"],
                "confidence": label["confidence"],
                "rationale": label["rationale"],
                "representative_terms": terms,
                "generated_by": "OpenAI",
            }
        )
    return sorted(validated, key=lambda item: expected_ids.index(item["topic_id"]))


def label_batch(topics: List[Dict[str, Any]], assigned_labels: List[Dict[str, str]], model: str, mock_response: Optional[str]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if mock_response:
        with open(mock_response, encoding="utf-8") as input_file:
            response = json.load(input_file)
        labels = validate_labels(response, topics)
        return labels, response.get("summary", {})

    prompt = build_prompt(topics, assigned_labels)
    response = call_openai(prompt, model)
    try:
        labels = validate_labels(response, topics)
        return labels, response.get("summary", {})
    except ValueError as first_error:
        log.warning("Validation failed, retrying once: %s", first_error)
        repair_prompt = (
            prompt
            + "\n\nThe previous response failed validation:\n"
            + str(first_error)
            + "\nReturn a corrected complete JSON object for this same batch."
        )
        repaired = call_openai(repair_prompt, model)
        labels = validate_labels(repaired, topics)
        return labels, repaired.get("summary", {})


def write_jsonl(path: str, labels: Iterable[Dict[str, Any]]) -> None:
    with open_text(path, "wt") as output_file:
        for label in labels:
            output_file.write(json.dumps(label, ensure_ascii=False) + "\n")


def print_summary(labels: List[Dict[str, Any]], summaries: List[Dict[str, Any]]) -> None:
    confidence_counts = Counter(label["confidence"] for label in labels)
    ocr_noise = [label["topic_id"] for label in labels if label["topic_type"] == "ocr_noise"]
    mixed = [label["topic_id"] for label in labels if label["topic_type"] == "mixed_uncertain"]
    resolved = []
    for summary in summaries:
        resolved.extend(summary.get("duplicate_labels_resolved", []))
    print(f"topics processed: {len(labels)}", file=sys.stderr)
    print(
        "confidence: "
        f"high={confidence_counts['high']} "
        f"medium={confidence_counts['medium']} "
        f"low={confidence_counts['low']}",
        file=sys.stderr,
    )
    print(f"ocr_noise topics: {len(ocr_noise)} {ocr_noise}", file=sys.stderr)
    print(f"mixed_uncertain topics: {len(mixed)} {mixed}", file=sys.stderr)
    print(f"duplicate or near-duplicate labels resolved: {resolved}", file=sys.stderr)


def main(argv: Optional[Sequence[str]] = None) -> int:
    if dotenv is not None:
        dotenv.load_dotenv()
    args = parse_args(argv)
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)-15s %(filename)s:%(lineno)d %(levelname)s: %(message)s",
        force=True,
    )
    if assert_can_write_uri is not None:
        assert_can_write_uri(args.output, force_s3_overwrite=args.force_s3_overwrite)
    elif args.output.startswith("s3://"):
        raise RuntimeError(
            "S3 output requires smart_open and the cookbook Python helpers"
        )
    topics = read_topics(args.input, args.top_terms)
    batches = make_batches(topics, args.max_prompt_chars, args.max_topics_per_batch)
    log.info("Read %d topics; processing in %d batch(es)", len(topics), len(batches))

    all_labels: List[Dict[str, Any]] = []
    summaries: List[Dict[str, Any]] = []
    assigned_labels: List[Dict[str, str]] = []
    for batch_number, batch in enumerate(batches, 1):
        log.info("Labeling batch %d/%d with %d topics", batch_number, len(batches), len(batch))
        labels, summary = label_batch(batch, assigned_labels, args.model, args.mock_response)
        all_labels.extend(labels)
        summaries.append(summary)
        assigned_labels.extend(
            {
                "topic_id": label["topic_id"],
                "label_short": label["label_short"],
                "topic_type": label["topic_type"],
            }
            for label in labels
        )

    validate_labels({"labels": all_labels}, topics)
    write_jsonl(args.output, all_labels)
    print_summary(all_labels, summaries)
    return 0


if __name__ == "__main__":
    sys.exit(main())
