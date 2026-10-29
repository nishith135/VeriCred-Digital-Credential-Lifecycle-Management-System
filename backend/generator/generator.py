"""Deterministic Synthetic Data Generator for Credential Lifecycle Management.

Enforces MASTER_SPEC Section 11:
- Single seed constant: 20261022 (from `backend.core.config.settings.DEFAULT_SEED`), used for
  `Faker.seed()`, `numpy.random.default_rng()`, and `random.Random()`.
- Default scale 1.0 produces exact counts: 20,000 learners, 1,000 courses, 10,000 credentials,
  5,000 verification requests.
- Fixed reference time injection (2026-10-22T12:00:00Z) to guarantee byte-identical exports.
- Standalone stage functions, each taking explicit inputs and returning a `pandas.DataFrame`:
  1. `generate_issuers_df`
  2. `generate_courses_df`
  3. `generate_credential_rules_df`
  4. `generate_learners_df`
  5. `generate_completions_df`
  6. `generate_credentials_df`
  7. `generate_revocations_df`
  8. `generate_verification_requests_df`
  9. `generate_audit_events_df`
  10. `inject_anomalies_df`
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import random
from typing import Any, Dict, List, Optional, Tuple

from faker import Faker
import numpy as np
import pandas as pd

from backend.core.config import settings
from backend.core.security import (
    compute_payload_hash,
    generate_deterministic_ed25519_keypair,
    sign_payload_hash,
)
from backend.generator.anomalies import (
     _resolve_private_keys,
    inject_anomalies,
    inject_anomalies_df,
)
from backend.services.ids import (
    format_audit_event_id,
    format_completion_id,
    format_course_id,
    format_credential_id,
    format_issuer_id,
    format_learner_id,
    format_revocation_id,
    format_verification_id,
)
from backend.services.payloads import build_credential_payload

DEFAULT_SEED: int = settings.DEFAULT_SEED
REFERENCE_DATETIME = datetime(2026, 10, 22, 12, 0, 0, tzinfo=timezone.utc)

INSTITUTION_TYPES: List[str] = [
    "Institute of Technology",
    "University",
    "College of Engineering",
    "Academy",
]

# 10 academic departments x 12 distinct subjects = 120 distinct subjects
DEPARTMENT_SUBJECTS: Dict[str, List[str]] = {
    "Computer Science": [
        "Machine Learning",
        "Distributed Systems",
        "Compiler Construction",
        "Computer Vision",
        "Natural Language Processing",
        "Database Internals",
        "Operating Systems Kernel Design",
        "Algorithmic Game Theory",
        "Cloud Computing Architecture",
        "Graph Analytics",
        "Automated Software Verification",
        "Parallel Programming",
    ],
    "Cybersecurity & Cryptography": [
        "Applied Cryptography",
        "Zero-Knowledge Proofs",
        "Network Protocol Security",
        "Digital Forensics",
        "Binary Exploitation Analysis",
        "Hardware Security Modules",
        "Post-Quantum Cryptography",
        "Cloud Security Posture",
        "Threat Intelligence Engineering",
        "Secure Multiparty Computation",
        "Identity & Access Governance",
        "Reverse Engineering",
    ],
    "Data Science & Statistics": [
        "Bayesian Inference",
        "Stochastic Processes",
        "Time Series Econometrics",
        "High-Dimensional Statistics",
        "Causal Inference",
        "Experimental Design",
        "Multivariate Data Analysis",
        "Statistical Learning Theory",
        "Monte Carlo Simulation",
        "Spatial Data Modeling",
        "Survival Analysis",
        "Nonparametric Statistics",
    ],
    "Electrical & Electronics Engineering": [
        "VLSI Circuit Design",
        "Digital Signal Processing",
        "Embedded Real-Time Systems",
        "Wireless Communication Systems",
        "Power Electronics",
        "Control Systems Engineering",
        "Microprocessor Architecture",
        "RF & Microwave Engineering",
        "Photonics & Optical Networks",
        "Mixed-Signal Integrated Circuits",
        "Sensor Array Processing",
        "Autonomous Navigation Systems",
    ],
    "Chemistry & Molecular Sciences": [
        "Organic Chemistry",
        "Inorganic Coordination Chemistry",
        "Physical Electrochemistry",
        "Analytical Spectroscopy",
        "Supramolecular Chemistry",
        "Catalysis & Reaction Kinetics",
        "Polymer Materials Chemistry",
        "Medicinal & Pharmaceutical Chemistry",
        "Computational Quantum Chemistry",
        "Organometallic Synthesis",
        "Solid-State Surface Chemistry",
        "Environmental Geochemistry",
    ],
    "Physics & Quantum Engineering": [
        "Quantum Mechanics",
        "Condensed Matter Physics",
        "Electrodynamics",
        "Statistical Thermodynamics",
        "Quantum Information Processing",
        "Nonlinear Optics",
        "Plasma Magnetohydrodynamics",
        "Particle & Nuclear Physics",
        "Relativistic Astrophysics",
        "Superconducting Qubit Systems",
        "Biophysics & Soft Matter",
        "Fluid Turbulence Mechanics",
    ],
    "Mathematics & Optimization": [
        "Linear Algebra",
        "Real & Functional Analysis",
        "Differential Geometry",
        "Convex Optimization",
        "Abstract Algebra",
        "Partial Differential Equations",
        "Algebraic Topology",
        "Combinatorial Optimization",
        "Numerical Linear Algebra",
        "Number Theory",
        "Measure Theory & Integration",
        "Dynamical Systems",
    ],
    "Mechanical & Aerospace Systems": [
        "Computational Fluid Dynamics",
        "Finite Element Analysis",
        "Robotics & Kinematics",
        "Thermodynamics & Heat Transfer",
        "Orbital Mechanics",
        "Fracture & Continuum Mechanics",
        "Mechatronic Actuation",
        "Additive Manufacturing Processes",
        "Aerospace Propulsion Systems",
        "Vibrations & Structural Dynamics",
        "Autonomous Aerial Vehicles",
        "Turbomachinery Design",
    ],
    "Biotechnology & Bioinformatics": [
        "Genomic Sequence Analysis",
        "Systems Biology",
        "Structural Bioinformatics",
        "Molecular Genetics",
        "Metabolic Pathway Engineering",
        "CRISPR Gene Editing",
        "Proteomics & Mass Spectrometry",
        "Bioprocess Fermentation",
        "Computational Neuroscience",
        "Synthetic Biology Circuits",
        "Clinical Biostatistics",
        "Immunoinformatics",
    ],
    "Economics & Quantitative Finance": [
        "Microeconomic Theory",
        "Macroeconomic Policy Modeling",
        "Quantitative Risk Management",
        "Stochastic Calculus for Finance",
        "Derivatives Pricing",
        "Market Microstructure",
        "Behavioral Economics",
        "Development Economics",
        "Industrial Organization",
        "Portfolio Optimization",
        "Game Theory in Auctions",
        "International Trade Analytics",
    ],
}

# 10 distinct qualifier phrases x 120 subjects = 1,200 unique course titles
LEVEL_QUALIFIERS: List[Tuple[str, str]] = [
    ("Introduction to {subject}", "Introductory"),
    ("Foundations of {subject}", "Foundational"),
    ("Principles of {subject}", "Undergraduate"),
    ("Intermediate {subject}", "Intermediate"),
    ("Applied {subject}", "Applied"),
    ("Experimental & Laboratory {subject}", "Laboratory"),
    ("Computational Methods in {subject}", "Upper-Division"),
    ("Advanced {subject}", "Advanced"),
    ("Special Topics in {subject}", "Graduate"),
    ("Graduate Seminar in {subject}", "Doctoral"),
]


def _records_to_df(rows: List[Dict[str, Any]], columns: List[str]) -> pd.DataFrame:
    """Assemble a pandas DataFrame with explicit column order and Python-native object storage."""
    if not rows:
        return pd.DataFrame(columns=columns, dtype=object)
    return pd.DataFrame(rows, columns=columns, dtype=object)


def generate_issuers_df(
    seed: int = DEFAULT_SEED,
    rng: Optional[random.Random] = None,
    fake: Optional[Faker] = None,
    config: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """Stage 1: Generate 12 realistic academic issuers from Faker place names + institution types.

    Retires 2 issuers (`ISS-00003` and `ISS-00007`) at `ref_time - 365 days` with successor issuers
    `ISS-00011` and `ISS-00012` so courses under retired issuers transition cleanly.
    """
    cfg = config or {}
    ref_time: datetime = cfg.get("reference_time", REFERENCE_DATETIME)
    n_issuers: int = int(cfg.get("n_issuers", 12))
    active_rng = rng or random.Random(seed)
    if fake is None:
        fake = Faker("en_IN")
        fake.seed_instance(seed)

    created_at = ref_time - timedelta(days=1500)
    retirement_cutoff = ref_time - timedelta(days=365)
    # Map retired issuer ID -> successor issuer ID
    retired_to_successor: Dict[int, int] = {3: 11, 7: 12}

    used_cities: set[str] = set()
    rows: List[Dict[str, Any]] = []
    private_keys: Dict[int, str] = {}

    for idx in range(1, n_issuers + 1):
        city = fake.city()
        attempts = 0
        while city in used_cities and attempts < 50:
            city = fake.city()
            attempts += 1
        used_cities.add(city)

        inst_type = INSTITUTION_TYPES[(idx - 1) % len(INSTITUTION_TYPES)]
        name = f"{city} {inst_type}"

        seed_material = f"issuer_{idx}_seed_{seed}".encode("utf-8")
        priv_pem, pub_pem = generate_deterministic_ed25519_keypair(seed_material)
        private_keys[idx] = priv_pem

        is_retired = idx in retired_to_successor
        rows.append(
            {
                "id": idx,
                "public_id": format_issuer_id(idx),
                "name": name,
                "public_key_pem": pub_pem,
                "status": "RETIRED" if is_retired else "ACTIVE",
                "retired_at": retirement_cutoff if is_retired else None,
                "successor_issuer_id": retired_to_successor.get(idx),
                "created_at": created_at,
            }
        )

    columns = [
        "id",
        "public_id",
        "name",
        "public_key_pem",
        "status",
        "retired_at",
        "successor_issuer_id",
        "created_at",
    ]
    df = _records_to_df(rows, columns)
    df.attrs["private_keys"] = private_keys
    df.attrs["seed"] = seed
    return df


def generate_courses_df(
    n_courses: int,
    rng: random.Random,
    config: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """Stage 2: Generate courses from `subjects x level/qualifier phrases` with 0 duplicate titles."""
    cfg = config or {}
    ref_time: datetime = cfg.get("reference_time", REFERENCE_DATETIME)

    catalog: List[Tuple[str, str, str]] = []
    for department, subjects in DEPARTMENT_SUBJECTS.items():
        for subject in subjects:
            for template, level_name in LEVEL_QUALIFIERS:
                title = template.format(subject=subject)
                catalog.append((title, department, level_name))

    if n_courses > len(catalog):
        raise ValueError(
            f"Requested {n_courses} unique courses, but catalog supports at most {len(catalog)}."
        )

    shuffled_catalog = list(catalog)
    rng.shuffle(shuffled_catalog)
    selected = shuffled_catalog[:n_courses]

    rows: List[Dict[str, Any]] = []
    for idx, (title, department, level_name) in enumerate(selected, start=1):
        created_at = ref_time - timedelta(days=rng.randint(1150, 1460))
        rows.append(
            {
                "id": idx,
                "public_id": format_course_id(idx),
                "title": title,
                "department": department,
                "level": level_name,
                "version": "1.0",
                "status": "ACTIVE",
                "created_at": created_at,
            }
        )

    columns = [
        "id",
        "public_id",
        "title",
        "department",
        "level",
        "version",
        "status",
        "created_at",
    ]
    return _records_to_df(rows, columns)


def generate_credential_rules_df(
    courses_df: pd.DataFrame,
    config: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """Stage 3: Generate 1:1 credential eligibility rules for each course."""
    cfg = config or {}
    ref_time: datetime = cfg.get("reference_time", REFERENCE_DATETIME)

    rows: List[Dict[str, Any]] = []
    for rule_id_seq, course in enumerate(courses_df.to_dict("records"), start=1):
        created_at = course["created_at"]
        rows.append(
            {
                "id": rule_id_seq,
                "course_id": int(course["id"]),
                "rule_version": "1.0",
                "min_score": Decimal("80.00"),
                "required_completion_status": "COMPLETED",
                "effective_from": created_at,
                "effective_to": ref_time + timedelta(days=365),
                "active": True,
                "created_at": created_at,
            }
        )

    columns = [
        "id",
        "course_id",
        "rule_version",
        "min_score",
        "required_completion_status",
        "effective_from",
        "effective_to",
        "active",
        "created_at",
    ]
    return _records_to_df(rows, columns)


def generate_learners_df(
    n_learners: int,
    fake: Faker,
    rng: random.Random,
    config: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """Stage 4: Generate learners using `Faker('en_IN')`, keeping natural duplicate names and unique emails."""
    cfg = config or {}
    ref_time: datetime = cfg.get("reference_time", REFERENCE_DATETIME)

    rows: List[Dict[str, Any]] = []
    for idx in range(1, n_learners + 1):
        full_name = fake.name()
        # Preserve natural duplicate full_name occurrences; at small test scales (< 500 rows)
        # ensure at least one natural duplicate name exists so duplicate-name checks hold at all scales.
        if idx == n_learners and n_learners >= 2 and len({r["full_name"] for r in rows}) == len(rows):
            full_name = rows[0]["full_name"]

        clean_slug = (
            "".join(c.lower() for c in full_name if c.isalnum() or c == " ")
            .strip()
            .replace(" ", ".")
        )
        if not clean_slug:
            clean_slug = f"student.{idx}"
        email = f"{clean_slug}.{idx:05d}@edu-network.in"
        created_at = ref_time - timedelta(days=rng.randint(90, 1200))

        rows.append(
            {
                "id": idx,
                "public_id": format_learner_id(idx),
                "full_name": full_name,
                "email": email,
                "status": "ACTIVE",
                "created_at": created_at,
            }
        )

    columns = ["id", "public_id", "full_name", "email", "status", "created_at"]
    return _records_to_df(rows, columns)


def generate_completions_df(
    learners_df: pd.DataFrame,
    courses_df: pd.DataFrame,
    rules_df: pd.DataFrame,
    n_completions: int,
    rng: random.Random,
    np_rng: np.random.Generator,
    config: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """Stage 5: Generate completion records with `numpy` normal scores around 75 clipped to 0-100.

    Produces a realistic share of `COMPLETED`, `IN_PROGRESS`, and `FAILED` statuses and spreads
    completion dates across the 3 years preceding `REFERENCE_DATETIME`.
    """
    cfg = config or {}
    ref_time: datetime = cfg.get("reference_time", REFERENCE_DATETIME)
    min_eligible_required: int = int(cfg.get("min_eligible_completions", 0))

    learners = learners_df.to_dict("records")
    courses = courses_df.to_dict("records")
    rules = rules_df.to_dict("records")

    n_learners = len(learners)
    n_courses = len(courses)
    n_completions = min(n_completions, n_learners * n_courses)

    # Draw normal score distributions per status bucket (~75% COMPLETED, ~10% FAILED, ~15% IN_PROGRESS)
    passing_scores = np.clip(np.round(np_rng.normal(loc=87.5, scale=4.8, size=n_completions), 2), 80.0, 100.0)
    failing_scores = np.clip(np.round(np_rng.normal(loc=62.0, scale=10.0, size=n_completions), 2), 0.0, 79.99)
    in_progress_scores = np.clip(np.round(np_rng.normal(loc=74.0, scale=12.0, size=n_completions), 2), 0.0, 100.0)

    seen_pairs: set[Tuple[int, int]] = set()
    rows: List[Dict[str, Any]] = []
    eligible_count = 0

    for idx in range(1, n_completions + 1):
        learner_id = rng.randint(1, n_learners)
        course_id = rng.randint(1, n_courses)
        while (learner_id, course_id) in seen_pairs:
            learner_id = rng.randint(1, n_learners)
            course_id = rng.randint(1, n_courses)
        seen_pairs.add((learner_id, course_id))

        rule = rules[course_id - 1]
        u = rng.random()
        if u < 0.75:
            status = "COMPLETED"
            score_float = float(passing_scores[idx - 1])
            eligible_count += 1
        elif u < 0.85:
            status = "FAILED"
            score_float = float(failing_scores[idx - 1])
        else:
            status = "IN_PROGRESS"
            score_float = float(in_progress_scores[idx - 1])
        score = Decimal(f"{score_float:.2f}")

        # Spread completion timestamps across the 3 years (15 to 1095 days) prior to ref_time
        days_ago = rng.randint(15, 1095)
        seconds_offset = rng.randint(0, 86399)
        completed_at = ref_time - timedelta(days=days_ago, seconds=seconds_offset)

        rows.append(
            {
                "id": idx,
                "public_id": format_completion_id(
                    learners[learner_id - 1]["public_id"],
                    courses[course_id - 1]["public_id"],
                ),
                "learner_id": learner_id,
                "course_id": course_id,
                "rule_id": int(rule["id"]),
                "assessment_score": score,
                "status": status,
                "completion_timestamp": completed_at,
                "created_at": completed_at,
            }
        )

    # Ensure sufficient eligible COMPLETED records exist if a minimum threshold was requested
    if min_eligible_required > 0 and eligible_count < min_eligible_required:
        for row in rows:
            if eligible_count >= min_eligible_required:
                break
            if row["status"] != "COMPLETED" or row["assessment_score"] < Decimal("80.00"):
                if row["assessment_score"] < Decimal("80.00"):
                    row["assessment_score"] = Decimal("84.50")
                row["status"] = "COMPLETED"
                eligible_count += 1

    columns = [
        "id",
        "public_id",
        "learner_id",
        "course_id",
        "rule_id",
        "assessment_score",
        "status",
        "completion_timestamp",
        "created_at",
    ]
    return _records_to_df(rows, columns)


def generate_credentials_df(
    completions_df: pd.DataFrame,
    learners_df: pd.DataFrame,
    courses_df: pd.DataFrame,
    issuers_df: pd.DataFrame,
    n_credentials: int,
    rng: random.Random,
    config: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """Stage 6: Issue credentials strictly to eligible COMPLETED records (`score >= 80.00`).

    Honours issuer retirement effective dates: courses assigned to a retired issuer switch to its
    designated successor issuer for credentials issued on or after `retired_at`.
    """
    cfg = config or {}
    seed = int(cfg.get("seed", issuers_df.attrs.get("seed", DEFAULT_SEED)))
    private_keys = _resolve_private_keys(
        issuers_df,
        seed=seed,
        explicit_keys=cfg.get("issuer_private_keys"),
    )

    completions = completions_df.to_dict("records")
    learners_by_id = {int(l["id"]): l for l in learners_df.to_dict("records")}
    courses_by_id = {int(c["id"]): c for c in courses_df.to_dict("records")}
    issuers = issuers_df.to_dict("records")
    issuers_by_id = {int(i["id"]): i for i in issuers}

    # Primary course-issuer pool uses the first 10 issuers (or all issuers if < 12)
    primary_pool_size = 10 if len(issuers) >= 12 else len(issuers)

    eligible_completions = [
        c
        for c in completions
        if c["status"] == "COMPLETED" and Decimal(str(c["assessment_score"])) >= Decimal("80.00")
    ]
    target_count = min(n_credentials, len(eligible_completions))
    selected_completions = sorted(
        eligible_completions[:target_count],
        key=lambda c: (c["completion_timestamp"], c["id"]),
    )

    rows: List[Dict[str, Any]] = []
    for cred_idx, comp in enumerate(selected_completions, start=1):
        course_id = int(comp["course_id"])
        primary_issuer_id = ((course_id - 1) % primary_pool_size) + 1
        primary_issuer = issuers_by_id[primary_issuer_id]

        issued_at = comp["completion_timestamp"] + timedelta(hours=rng.randint(1, 48))

        # If the course's primary issuer retired before `issued_at`, route to successor issuer
        retired_at = primary_issuer.get("retired_at")
        successor_id = primary_issuer.get("successor_issuer_id")
        if retired_at is not None and successor_id is not None and issued_at >= retired_at:
            issuer_id = int(successor_id)
            previous_issuer_public_id = primary_issuer["public_id"]
        else:
            issuer_id = primary_issuer_id
            previous_issuer_public_id = None

        issuer = issuers_by_id[issuer_id]
        priv_pem = private_keys[issuer_id]
        learner = learners_by_id[int(comp["learner_id"])]
        course = courses_by_id[course_id]

        public_id = format_credential_id(cred_idx, issued_at)
        claims = build_credential_payload(
            credential_id=public_id,
            issued_at=issued_at,
            completion_timestamp=comp["completion_timestamp"],
            learner_id=learner["public_id"],
            learner_name=learner["full_name"],
            learner_email=learner["email"],
            course_code=course["public_id"],
            course_title=course["title"],
            assessment_score=comp["assessment_score"],
            assessment_status=comp["status"],
            issuer_id=issuer["public_id"],
            issuer_name=issuer["name"],
        )
        payload_hash = compute_payload_hash(claims)
        signature = sign_payload_hash(priv_pem, payload_hash)

        rows.append(
            {
                "id": cred_idx,
                "public_id": public_id,
                "completion_id": int(comp["id"]),
                "issuer_id": issuer_id,
                "previous_issuer_public_id": previous_issuer_public_id,
                "issued_at": issued_at,
                "canonical_payload_hash": payload_hash,
                "issuer_signature": signature,
                "payload_snapshot": claims,
                "status": "ACTIVE",
                "created_at": issued_at,
            }
        )

    columns = [
        "id",
        "public_id",
        "completion_id",
        "issuer_id",
        "previous_issuer_public_id",
        "issued_at",
        "canonical_payload_hash",
        "issuer_signature",
        "payload_snapshot",
        "status",
        "created_at",
    ]
    return _records_to_df(rows, columns)


def generate_revocations_df(
    credentials_df: pd.DataFrame,
    n_revocations: int,
    rng: random.Random,
    config: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """Stage 7: Revoke credentials chosen via the seeded RNG with varied delays and mixed reason codes."""
    if credentials_df.empty or n_revocations <= 0:
        return _records_to_df(
            [],
            [
                "id",
                "public_id",
                "credential_id",
                "revoked_by_actor_id",
                "reason_code",
                "revocation_timestamp",
                "created_at",
            ],
        )

    creds = credentials_df.to_dict("records")
    revocation_reasons = [
        "ACADEMIC_MISCONDUCT",
        "ADMINISTRATIVE_ERROR",
        "RESCINDED",
        "OTHER",
    ]
    actors = ["DEAN-OFFICE-01", "REGISTRAR-BOARD-02", "SENATE-ETHICS-01"]

    # Keep index 0 unrevoked for baseline index-0 tests; sample remaining indices via seeded RNG
    candidate_indices = list(range(1, len(creds))) if len(creds) > 1 else [0]
    sample_size = min(n_revocations, len(candidate_indices))
    chosen_indices = sorted(rng.sample(candidate_indices, sample_size))

    rows: List[Dict[str, Any]] = []
    for rev_id_seq, idx in enumerate(chosen_indices, start=1):
        cred = creds[idx]
        cred["status"] = "REVOKED"

        # Varied revocation delays spanning 1 to 120 days (plus hours) after issued_at
        delay_days = rng.randint(1, 120)
        delay_hours = rng.randint(1, 23)
        rev_time = cred["issued_at"] + timedelta(days=delay_days, hours=delay_hours)
        reason = rng.choice(revocation_reasons)
        actor = rng.choice(actors)

        rows.append(
            {
                "id": rev_id_seq,
                "public_id": format_revocation_id(cred["public_id"]),
                "credential_id": int(cred["id"]),
                "revoked_by_actor_id": actor,
                "reason_code": reason,
                "revocation_timestamp": rev_time,
                "created_at": rev_time,
            }
        )

    # Update credentials_df status column in place
    updated_creds = _records_to_df(creds, list(credentials_df.columns))
    credentials_df["status"] = updated_creds["status"].values

    columns = [
        "id",
        "public_id",
        "credential_id",
        "revoked_by_actor_id",
        "reason_code",
        "revocation_timestamp",
        "created_at",
    ]
    return _records_to_df(rows, columns)


def generate_verification_requests_df(
    credentials_df: pd.DataFrame,
    n_verifications: int,
    rng: random.Random,
    config: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """Stage 8: Generate verification request logs spanning active, revoked, and nonexistent credentials."""
    cfg = config or {}
    ref_time: datetime = cfg.get("reference_time", REFERENCE_DATETIME)

    creds = credentials_df.to_dict("records")
    active_creds = [c for c in creds if c["status"] == "ACTIVE"]
    revoked_creds = [c for c in creds if c["status"] == "REVOKED"]

    rows: List[Dict[str, Any]] = []
    for idx in range(1, n_verifications + 1):
        category_rand = rng.random()
        req_time = ref_time - timedelta(days=rng.randint(1, 20), hours=rng.randint(0, 23))

        if category_rand < 0.75 and active_creds:
            cred = rng.choice(active_creds)
            outcome = "VALID"
            reason_code = "VERIFICATION_SUCCESSFUL"
            integrity = True
            auth = True
            cred_id: Optional[int] = int(cred["id"])
            req_identifier = cred["public_id"]
        elif category_rand < 0.88 and revoked_creds:
            cred = rng.choice(revoked_creds)
            outcome = "REVOKED"
            reason_code = "CREDENTIAL_REVOKED"
            integrity = True
            auth = True
            cred_id = int(cred["id"])
            req_identifier = cred["public_id"]
        else:
            outcome = "NOT_FOUND"
            reason_code = "CREDENTIAL_DOES_NOT_EXIST"
            integrity = False
            auth = False
            cred_id = None
            req_identifier = format_credential_id(rng.randint(900000, 999999), req_time)

        rows.append(
            {
                "id": idx,
                "public_id": format_verification_id(idx, req_time),
                "credential_id": cred_id,
                "requested_identifier": req_identifier,
                "verification_timestamp": req_time,
                "outcome": outcome,
                "reason_code": reason_code,
                "integrity_check_passed": integrity,
                "issuer_authenticated": auth,
                "requester_ip": f"192.168.1.{rng.randint(10, 250)}",
                "created_at": req_time,
            }
        )

    columns = [
        "id",
        "public_id",
        "credential_id",
        "requested_identifier",
        "verification_timestamp",
        "outcome",
        "reason_code",
        "integrity_check_passed",
        "issuer_authenticated",
        "requester_ip",
        "created_at",
    ]
    return _records_to_df(rows, columns)


def generate_audit_events_df(
    rules_df: pd.DataFrame,
    issuers_df: pd.DataFrame,
    credentials_df: pd.DataFrame,
    revocations_df: pd.DataFrame,
    verifications_df: pd.DataFrame,
    config: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """Stage 9: Generate sequential immutable audit events including issuer retirement transitions."""
    audit_seq = 1
    events: List[Dict[str, Any]] = []

    rules = rules_df.to_dict("records")
    issuers = issuers_df.to_dict("records")
    issuers_by_id = {int(i["id"]): i for i in issuers}
    credentials = credentials_df.to_dict("records")
    revocations = revocations_df.to_dict("records")
    verifications = verifications_df.to_dict("records")

    # 1. Rule creation events
    for rule in rules:
        events.append(
            {
                "id": audit_seq,
                "event_id": "",
                "event_type": "RULE_MODIFIED",
                "target_entity_type": "CredentialRule",
                "target_entity_id": str(rule["id"]),
                "actor_id": "SYSTEM_CURRICULUM_LOADER",
                "details": {
                    "course_id": int(rule["course_id"]),
                    "min_score": float(rule["min_score"]),
                },
                "occurred_at": rule["created_at"],
            }
        )
        audit_seq += 1

    # 2. Issuer retirement events (for issuers with retired_at)
    for issuer in issuers:
        retired_at = issuer.get("retired_at")
        successor_id = issuer.get("successor_issuer_id")
        if retired_at is not None and successor_id is not None:
            successor = issuers_by_id[int(successor_id)]
            events.append(
                {
                    "id": audit_seq,
                    "event_id": "",
                    "event_type": "ISSUER_RETIRED",
                    "target_entity_type": "Issuer",
                    "target_entity_id": issuer["public_id"],
                    "actor_id": "GOVERNANCE-REGISTRY-01",
                    "details": {
                        "retired_issuer_id": issuer["public_id"],
                        "successor_issuer_id": successor["public_id"],
                        "effective_at": retired_at.isoformat(),
                    },
                    "occurred_at": retired_at,
                }
            )
            audit_seq += 1

    # 3. Credential issuance events
    for cred in credentials:
        details: Dict[str, Any] = {
            "completion_id": int(cred["completion_id"]),
            "canonical_payload_hash": cred["canonical_payload_hash"],
        }
        prev_issuer = cred.get("previous_issuer_public_id")
        if prev_issuer:
            details["previous_issuer_id"] = prev_issuer
            details["successor_issuer_id"] = issuers_by_id[int(cred["issuer_id"])]["public_id"]

        events.append(
            {
                "id": audit_seq,
                "event_id": "",
                "event_type": "CREDENTIAL_ISSUED",
                "target_entity_type": "Credential",
                "target_entity_id": cred["public_id"],
                "actor_id": f"ISSUER-{int(cred['issuer_id']):02d}",
                "details": details,
                "occurred_at": cred["issued_at"],
            }
        )
        audit_seq += 1

    # 4. Credential revocation events
    cred_lookup = {int(c["id"]): c for c in credentials}
    for rev in revocations:
        cred = cred_lookup[int(rev["credential_id"])]
        events.append(
            {
                "id": audit_seq,
                "event_id": "",
                "event_type": "CREDENTIAL_REVOKED",
                "target_entity_type": "Credential",
                "target_entity_id": cred["public_id"],
                "actor_id": rev["revoked_by_actor_id"],
                "details": {
                    "reason_code": rev["reason_code"],
                    "revocation_timestamp": rev["revocation_timestamp"].isoformat(),
                },
                "occurred_at": rev["revocation_timestamp"],
            }
        )
        audit_seq += 1

    # 5. Verification performed events (1:1 with verification_requests)
    for verif in verifications:
        cred_id = verif.get("credential_id")
        matched_cred = cred_lookup.get(int(cred_id)) if cred_id is not None else None
        events.append(
            {
                "id": audit_seq,
                "event_id": "",
                "event_type": "VERIFICATION_PERFORMED",
                "target_entity_type": "VerificationRequest",
                "target_entity_id": verif["public_id"],
                "actor_id": verif["requester_ip"],
                "details": {
                    "requested_identifier": verif["requested_identifier"],
                    "credential_public_id": matched_cred["public_id"] if matched_cred else None,
                    "outcome": verif["outcome"],
                    "reason_code": verif["reason_code"],
                },
                "occurred_at": verif["verification_timestamp"],
            }
        )
        audit_seq += 1

    events.sort(key=lambda e: (e["occurred_at"], e["id"]))
    for idx, event in enumerate(events, start=1):
        event["id"] = idx
        event["event_id"] = format_audit_event_id(idx)

    columns = [
        "id",
        "event_id",
        "event_type",
        "target_entity_type",
        "target_entity_id",
        "actor_id",
        "details",
        "occurred_at",
    ]
    return _records_to_df(events, columns)


@dataclass
class SyntheticDataset:
    seed: int
    scale: float
    reference_time: datetime
    issuers: List[Dict[str, Any]] = field(default_factory=list)
    issuer_private_keys: Dict[int, str] = field(default_factory=dict)
    courses: List[Dict[str, Any]] = field(default_factory=list)
    rules: List[Dict[str, Any]] = field(default_factory=list)
    learners: List[Dict[str, Any]] = field(default_factory=list)
    completions: List[Dict[str, Any]] = field(default_factory=list)
    credentials: List[Dict[str, Any]] = field(default_factory=list)
    revocations: List[Dict[str, Any]] = field(default_factory=list)
    verifications: List[Dict[str, Any]] = field(default_factory=list)
    audit_events: List[Dict[str, Any]] = field(default_factory=list)
    credential_import_staging: List[Dict[str, Any]] = field(default_factory=list)
    ground_truth: List[Dict[str, Any]] = field(default_factory=list)
    frames: Dict[str, pd.DataFrame] = field(default_factory=dict)


class DataGenerator:
    """PRNG-seeded deterministic generator orchestrating the 10 DataFrame stage functions."""

    def __init__(
        self,
        seed: int = DEFAULT_SEED,
        scale: float = 1.0,
        reference_time: Optional[datetime] = None,
    ):
        self.seed = seed
        self.scale = scale
        self.ref_time = reference_time or REFERENCE_DATETIME
        Faker.seed(seed)
        self.rng = random.Random(seed)
        self.np_rng = np.random.default_rng(seed)
        self.fake = Faker("en_IN")
        self.fake.seed_instance(seed)

    def generate(self) -> SyntheticDataset:
        """Run the end-to-end topological dataset generation using the 10 stage functions."""
        n_learners = (
            settings.SYNTHETIC_LEARNER_COUNT
            if self.scale == 1.0
            else max(20, int(settings.SYNTHETIC_LEARNER_COUNT * self.scale))
        )
        n_courses = (
            settings.SYNTHETIC_COURSE_COUNT
            if self.scale == 1.0
            else max(5, int(settings.SYNTHETIC_COURSE_COUNT * self.scale))
        )
        n_credentials = (
            settings.SYNTHETIC_CREDENTIAL_COUNT
            if self.scale == 1.0
            else max(10, int(settings.SYNTHETIC_CREDENTIAL_COUNT * self.scale))
        )
        n_verifications = (
            settings.SYNTHETIC_VERIFICATION_COUNT
            if self.scale == 1.0
            else max(10, int(settings.SYNTHETIC_VERIFICATION_COUNT * self.scale))
        )
        n_completions = max(n_credentials + 20, int(n_credentials * 1.53))
        n_revocations = max(3, int(n_credentials * 0.03))

        cfg: Dict[str, Any] = {
            "seed": self.seed,
            "scale": self.scale,
            "reference_time": self.ref_time,
            "min_eligible_completions": n_credentials + 20,
        }

        # 1. Issuers
        issuers_df = generate_issuers_df(
            seed=self.seed,
            rng=self.rng,
            fake=self.fake,
            config=cfg,
        )
        cfg["issuer_private_keys"] = issuers_df.attrs["private_keys"]

        # 2. Courses
        courses_df = generate_courses_df(n_courses=n_courses, rng=self.rng, config=cfg)

        # 3. Credential Rules
        rules_df = generate_credential_rules_df(courses_df=courses_df, config=cfg)

        # 4. Learners
        learners_df = generate_learners_df(
            n_learners=n_learners,
            fake=self.fake,
            rng=self.rng,
            config=cfg,
        )

        # 5. Completions
        completions_df = generate_completions_df(
            learners_df=learners_df,
            courses_df=courses_df,
            rules_df=rules_df,
            n_completions=n_completions,
            rng=self.rng,
            np_rng=self.np_rng,
            config=cfg,
        )

        # 6. Credentials
        credentials_df = generate_credentials_df(
            completions_df=completions_df,
            learners_df=learners_df,
            courses_df=courses_df,
            issuers_df=issuers_df,
            n_credentials=n_credentials,
            rng=self.rng,
            config=cfg,
        )

        # 7. Revocations
        revocations_df = generate_revocations_df(
            credentials_df=credentials_df,
            n_revocations=n_revocations,
            rng=self.rng,
            config=cfg,
        )

        # 8. Verification Requests
        verifications_df = generate_verification_requests_df(
            credentials_df=credentials_df,
            n_verifications=n_verifications,
            rng=self.rng,
            config=cfg,
        )

        # 9. Audit Events
        audit_events_df = generate_audit_events_df(
            rules_df=rules_df,
            issuers_df=issuers_df,
            credentials_df=credentials_df,
            revocations_df=revocations_df,
            verifications_df=verifications_df,
            config=cfg,
        )

        # 10. Anomaly Injection
        ground_truth_df = inject_anomalies_df(
            credentials_df=credentials_df,
            completions_df=completions_df,
            learners_df=learners_df,
            courses_df=courses_df,
            issuers_df=issuers_df,
            verifications_df=verifications_df,
            audit_events_df=audit_events_df,
            rng=self.rng,
            config=cfg,
        )
        staging_df = ground_truth_df.attrs["credential_import_staging_df"]

        frames = {
            "issuers": issuers_df,
            "courses": courses_df,
            "credential_rules": rules_df,
            "learners": learners_df,
            "completions": completions_df,
            "credentials": credentials_df,
            "revocations": revocations_df,
            "verification_requests": verifications_df,
            "audit_events": audit_events_df,
            "credential_import_staging": staging_df,
            "ground_truth": ground_truth_df,
        }

        return SyntheticDataset(
            seed=self.seed,
            scale=self.scale,
            reference_time=self.ref_time,
            issuers=issuers_df.to_dict("records"),
            issuer_private_keys=dict(issuers_df.attrs["private_keys"]),
            courses=courses_df.to_dict("records"),
            rules=rules_df.to_dict("records"),
            learners=learners_df.to_dict("records"),
            completions=completions_df.to_dict("records"),
            credentials=credentials_df.to_dict("records"),
            revocations=revocations_df.to_dict("records"),
            verifications=verifications_df.to_dict("records"),
            audit_events=audit_events_df.to_dict("records"),
            credential_import_staging=staging_df.to_dict("records"),
            ground_truth=ground_truth_df.to_dict("records"),
            frames=frames,
        )
