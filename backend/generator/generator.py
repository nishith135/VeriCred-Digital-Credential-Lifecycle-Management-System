"""Deterministic Synthetic Data Generator for Credential Lifecycle Management.

Enforces MASTER_SPEC Section 11:
- Default seed: 20261022.
- Scales: default 1.0 (20,000 learners, 1,000 courses, 10,000 credentials, 5,000 verifications).
- Fixed reference time injection (2026-10-22T12:00:00Z) to guarantee identical outputs across environments.
- Strict topological generation order:
  1. Issuers, Courses, CredentialRules, Learners
  2. CompletionRecords (satisfying eligibility ratios)
  3. Credentials (strictly issued to eligible completions)
  4. Revocations and VerificationRequests
  5. AuditEvents
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import random
from typing import Any, Dict, List, Optional, Tuple

from faker import Faker

from backend.core.security import (
    compute_payload_hash,
    generate_deterministic_ed25519_keypair,
    generate_ed25519_keypair,
    sign_payload_hash,
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

DEFAULT_SEED = 20261022
REFERENCE_DATETIME = datetime(2026, 10, 22, 12, 0, 0, tzinfo=timezone.utc)


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


COURSE_SPECIALIZATIONS = [
    "Advanced Cryptography & Zero-Knowledge Proofs",
    "Distributed Cloud Architecture & High Availability",
    "Full-Stack Machine Learning Engineering",
    "Scalable Data Pipelines & Stream Processing",
    "Offensive Cybersecurity & Penetration Testing",
    "Quantum Computing Algorithms & Qiskit",
    "Microservices & Kubernetes Orchestration",
    "Deep Learning & Transformer Architectures",
    "Database Internals & Concurrency Control",
    "Autonomous Robotics, SLAM & Computer Vision",
    "Digital Forensics & Incident Response",
    "High-Frequency Quantitative Systems",
    "Software Verification & Formal Methods",
    "Mobile Computing & Cross-Platform Architecture",
    "Embedded Real-Time Operating Systems (RTOS)",
    "Natural Language Processing & Large Language Models",
    "Network Security & Secure Protocols Design",
    "Decentralized Systems & Smart Contract Auditing",
    "Applied AI in Healthcare & Bioinformatics",
    "Compiler Design & Programming Language Theory",
    "Computer Systems & Hardware Architecture",
    "DevSecOps Automation & Infrastructure as Code",
    "Applied Data Science with Python & R",
    "Graph Algorithms & Social Network Analysis",
    "Computer Graphics & Interactive Rendering",
]


class DataGenerator:
    """PRNG-seeded deterministic generator for the credential lifecycle dataset."""

    def __init__(
        self,
        seed: int = DEFAULT_SEED,
        scale: float = 1.0,
        reference_time: Optional[datetime] = None,
    ):
        self.seed = seed
        self.scale = scale
        self.ref_time = reference_time or REFERENCE_DATETIME
        self.rng = random.Random(seed)
        self.fake = Faker("en_IN")
        self.fake.seed_instance(seed)

    def generate(self) -> SyntheticDataset:
        """Run the end-to-end topological dataset generation."""
        dataset = SyntheticDataset(
            seed=self.seed,
            scale=self.scale,
            reference_time=self.ref_time,
        )

        # Target counts based on scale
        n_learners = max(20, int(20000 * self.scale))
        n_courses = max(5, int(1000 * self.scale))
        n_credentials = max(10, int(10000 * self.scale))
        n_verifications = max(10, int(5000 * self.scale))
        
        # 1. Issuers
        self._generate_issuers(dataset)
        
        # 2. Courses and Rules
        self._generate_courses_and_rules(dataset, n_courses)
        
        # 3. Learners
        self._generate_learners(dataset, n_learners)
        
        # 4. Completions (generate ~1.4x the required credentials to ensure enough eligible records)
        n_completions = max(n_credentials + 10, int(n_credentials * 1.4))
        self._generate_completions(dataset, n_completions)
        
        # 5. Credentials (strictly issued to eligible completions)
        self._generate_credentials(dataset, n_credentials)
        
        # 6. Revocations (~3% of credentials)
        n_revocations = max(2, int(len(dataset.credentials) * 0.03))
        self._generate_revocations(dataset, n_revocations)
        
        # 7. Verification Requests
        self._generate_verifications(dataset, n_verifications)
        
        # 8. Audit Events
        self._generate_audit_events(dataset)

        return dataset

    def _generate_issuers(self, dataset: SyntheticDataset) -> None:
        """Generate authorized academic institutions with Ed25519 cryptographic keypairs."""
        issuer_names = [
            "Indian Institute of Technology (IIT) Delhi",
            "Indian Institute of Science (IISc) Bengaluru",
            "National Institute of Technology (NIT) Trichy",
            "Birla Institute of Technology and Science (BITS) Pilani",
            "International Institute of Information Technology (IIIT) Hyderabad",
            "Delhi Technological University (DTU)",
            "Anna University College of Engineering",
        ]
        
        for idx, name in enumerate(issuer_names, start=1):
            seed_material = f"issuer_{idx}_seed_{self.seed}".encode("utf-8")
            priv_pem, pub_pem = generate_deterministic_ed25519_keypair(seed_material)
            created_at = self.ref_time - timedelta(days=730)
            
            issuer = {
                "id": idx,
                "public_id": format_issuer_id(idx),
                "name": name,
                "public_key_pem": pub_pem,
                "status": "ACTIVE",
                "created_at": created_at,
            }
            dataset.issuers.append(issuer)
            dataset.issuer_private_keys[idx] = priv_pem

    def _generate_courses_and_rules(self, dataset: SyntheticDataset, n_courses: int) -> None:
        """Generate course catalog and associated credential eligibility rules."""
        rule_id_seq = 1
        for idx in range(1, n_courses + 1):
            spec = self.rng.choice(COURSE_SPECIALIZATIONS)
            level = self.rng.choice(["101", "201", "301", "401", "501"])
            title = f"{spec} ({level})"
            created_at = self.ref_time - timedelta(days=self.rng.randint(300, 600))
            
            course = {
                "id": idx,
                "public_id": format_course_id(idx),
                "title": title,
                "version": "1.0",
                "status": "ACTIVE",
                "created_at": created_at,
            }
            dataset.courses.append(course)
            
            # Credential rule for this course
            rule = {
                "id": rule_id_seq,
                "course_id": idx,
                "rule_version": "1.0",
                "min_score": Decimal("80.00"),
                "required_completion_status": "COMPLETED",
                "effective_from": created_at,
                "effective_to": created_at + timedelta(days=1000),
                "active": True,
                "created_at": created_at,
            }
            dataset.rules.append(rule)
            rule_id_seq += 1

    def _generate_learners(self, dataset: SyntheticDataset, n_learners: int) -> None:
        """Generate learner master records with realistic variation and unique emails using Faker Indian locale."""
        for idx in range(1, n_learners + 1):
            full_name = self.fake.name()
            clean_slug = "".join(c.lower() for c in full_name if c.isalnum() or c == " ").strip().replace(" ", ".")
            if not clean_slug:
                clean_slug = f"student.{idx}"
            email = f"{clean_slug}.{idx:04d}@edu-network.in"
            created_at = self.ref_time - timedelta(days=self.rng.randint(60, 365))
            
            learner = {
                "id": idx,
                "public_id": format_learner_id(idx),
                "full_name": full_name,
                "email": email,
                "status": "ACTIVE",
                "created_at": created_at,
            }
            dataset.learners.append(learner)

    def _generate_completions(self, dataset: SyntheticDataset, n_completions: int) -> None:
        """Generate completion records with realistic score distributions.

        Each (learner, course) pair appears at most once because the completion
        public_id CMP-<learner>-<course> must be unique; colliding draws are re-drawn.
        """
        n_learners = len(dataset.learners)
        n_courses = len(dataset.courses)
        n_completions = min(n_completions, n_learners * n_courses)
        seen_pairs: set[tuple[int, int]] = set()
        
        for idx in range(1, n_completions + 1):
            learner_id = self.rng.randint(1, n_learners)
            course_id = self.rng.randint(1, n_courses)
            while (learner_id, course_id) in seen_pairs:
                learner_id = self.rng.randint(1, n_learners)
                course_id = self.rng.randint(1, n_courses)
            seen_pairs.add((learner_id, course_id))
            rule = dataset.rules[course_id - 1]
            
            # 75% pass rate (score >= 80.00, status COMPLETED), 25% fail / incomplete
            is_passing = self.rng.random() < 0.78
            if is_passing:
                score = round(Decimal(str(self.rng.uniform(80.00, 99.50))), 2)
                status = "COMPLETED"
            else:
                score = round(Decimal(str(self.rng.uniform(40.00, 79.50))), 2)
                status = self.rng.choice(["FAILED", "IN_PROGRESS"])
                
            completed_at = self.ref_time - timedelta(days=self.rng.randint(10, 180))
            
            completion = {
                "id": idx,
                "public_id": format_completion_id(
                    dataset.learners[learner_id - 1]["public_id"],
                    dataset.courses[course_id - 1]["public_id"],
                ),
                "learner_id": learner_id,
                "course_id": course_id,
                "rule_id": rule["id"],
                "assessment_score": score,
                "status": status,
                "completion_timestamp": completed_at,
                "created_at": completed_at,
            }
            dataset.completions.append(completion)

    def _generate_credentials(self, dataset: SyntheticDataset, n_credentials: int) -> None:
        """Issue credentials strictly to eligible completions."""
        eligible_completions = [
            c for c in dataset.completions
            if c["status"] == "COMPLETED" and c["assessment_score"] >= Decimal("80.00")
        ]
        
        target_count = min(n_credentials, len(eligible_completions))
        n_issuers = len(dataset.issuers)
        
        for cred_idx in range(1, target_count + 1):
            comp = eligible_completions[cred_idx - 1]
            issuer_id = ((cred_idx - 1) % n_issuers) + 1
            issuer = dataset.issuers[issuer_id - 1]
            priv_pem = dataset.issuer_private_keys[issuer_id]
            
            learner = dataset.learners[comp["learner_id"] - 1]
            course = dataset.courses[comp["course_id"] - 1]
            
            issued_at = comp["completion_timestamp"] + timedelta(
                hours=self.rng.randint(1, 48)
            )
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
            
            credential = {
                "id": cred_idx,
                "public_id": public_id,
                "completion_id": comp["id"],
                "issuer_id": issuer_id,
                "issued_at": issued_at,
                "canonical_payload_hash": payload_hash,
                "issuer_signature": signature,
                "payload_snapshot": claims,
                "status": "ACTIVE",
                "created_at": issued_at,
            }
            dataset.credentials.append(credential)

    def _generate_revocations(self, dataset: SyntheticDataset, n_revocations: int) -> None:
        """Revoke a deterministic fraction of credentials with valid reasons."""
        if not dataset.credentials:
            return
            
        revocation_reasons = ["ACADEMIC_MISCONDUCT", "ADMINISTRATIVE_ERROR", "RESCINDED"]
        rev_id_seq = 1
        
        step = max(1, len(dataset.credentials) // n_revocations)
        indices = list(range(0, len(dataset.credentials), step))[:n_revocations]
        
        for idx in indices:
            cred = dataset.credentials[idx]
            cred["status"] = "REVOKED"
            
            rev_time = cred["issued_at"] + timedelta(days=self.rng.randint(1, 15))
            reason = self.rng.choice(revocation_reasons)
            
            revocation = {
                "id": rev_id_seq,
                "public_id": format_revocation_id(cred["public_id"]),
                "credential_id": cred["id"],
                "revoked_by_actor_id": "DEAN-OFFICE-01",
                "reason_code": reason,
                "revocation_timestamp": rev_time,
                "created_at": rev_time,
            }
            dataset.revocations.append(revocation)
            rev_id_seq += 1

    def _generate_verifications(self, dataset: SyntheticDataset, n_verifications: int) -> None:
        """Generate verification request logs spanning active, revoked, and nonexistent credentials."""
        active_creds = [c for c in dataset.credentials if c["status"] == "ACTIVE"]
        revoked_creds = [c for c in dataset.credentials if c["status"] == "REVOKED"]
        
        for idx in range(1, n_verifications + 1):
            category_rand = self.rng.random()
            req_time = self.ref_time - timedelta(days=self.rng.randint(1, 20))
            
            if category_rand < 0.75 and active_creds:
                cred = self.rng.choice(active_creds)
                outcome = "VALID"
                reason_code = "VERIFICATION_SUCCESSFUL"
                integrity = True
                auth = True
                cred_id = cred["id"]
                req_identifier = cred["public_id"]
            elif category_rand < 0.88 and revoked_creds:
                cred = self.rng.choice(revoked_creds)
                outcome = "REVOKED"
                reason_code = "CREDENTIAL_REVOKED"
                integrity = True
                auth = True
                cred_id = cred["id"]
                req_identifier = cred["public_id"]
            else:
                outcome = "NOT_FOUND"
                reason_code = "CREDENTIAL_DOES_NOT_EXIST"
                integrity = False
                auth = False
                cred_id = None
                # Well-formed but never-issued identifier (issued numbers stay far below 900000)
                req_identifier = format_credential_id(self.rng.randint(900000, 999999), req_time)
                
            verification = {
                "id": idx,
                "public_id": format_verification_id(idx, req_time),
                "credential_id": cred_id,
                "requested_identifier": req_identifier,
                "verification_timestamp": req_time,
                "outcome": outcome,
                "reason_code": reason_code,
                "integrity_check_passed": integrity,
                "issuer_authenticated": auth,
                "requester_ip": f"192.168.1.{self.rng.randint(10, 250)}",
                "created_at": req_time,
            }
            dataset.verifications.append(verification)

    def _generate_audit_events(self, dataset: SyntheticDataset) -> None:
        """Create sequential immutable audit logs for all generated lifecycle actions."""
        audit_seq = 1
        
        # Rule creation events
        for rule in dataset.rules:
            dataset.audit_events.append({
                "id": audit_seq,
                "event_type": "RULE_MODIFIED",
                "target_entity_type": "CredentialRule",
                "target_entity_id": str(rule["id"]),
                "actor_id": "SYSTEM_CURRICULUM_LOADER",
                "details": {"course_id": rule["course_id"], "min_score": float(rule["min_score"])},
                "occurred_at": rule["created_at"],
            })
            audit_seq += 1
            
        # Credential issuance events
        for cred in dataset.credentials:
            dataset.audit_events.append({
                "id": audit_seq,
                "event_type": "CREDENTIAL_ISSUED",
                "target_entity_type": "Credential",
                "target_entity_id": cred["public_id"],
                "actor_id": f"ISSUER-{cred['issuer_id']:02d}",
                "details": {
                    "completion_id": cred["completion_id"],
                    "canonical_payload_hash": cred["canonical_payload_hash"],
                },
                "occurred_at": cred["issued_at"],
            })
            audit_seq += 1
            
        # Credential revocation events
        cred_lookup = {c["id"]: c for c in dataset.credentials}
        for rev in dataset.revocations:
            cred = cred_lookup[rev["credential_id"]]
            dataset.audit_events.append({
                "id": audit_seq,
                "event_type": "CREDENTIAL_REVOKED",
                "target_entity_type": "Credential",
                "target_entity_id": cred["public_id"],
                "actor_id": rev["revoked_by_actor_id"],
                "details": {
                    "reason_code": rev["reason_code"],
                    "revocation_timestamp": rev["revocation_timestamp"].isoformat(),
                },
                "occurred_at": rev["revocation_timestamp"],
            })
            audit_seq += 1

        # Verification performed events (1:1 with verification_requests)
        for verif in dataset.verifications:
            matched_cred = cred_lookup.get(verif["credential_id"]) if verif["credential_id"] else None
            dataset.audit_events.append({
                "id": audit_seq,
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
            })
            audit_seq += 1
            
        # Sort audit events deterministically by occurred_at
        dataset.audit_events.sort(key=lambda e: (e["occurred_at"], e["id"]))
        for idx, event in enumerate(dataset.audit_events, start=1):
            event["id"] = idx
            event["event_id"] = format_audit_event_id(idx)
