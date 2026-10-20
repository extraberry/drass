"""Idempotent seed: roles, lookups, demo users, synthetic demo research (PRD s44-45).
Run:  python -m server.app.seed [--no-demo]"""
import hashlib
import sys
import textwrap
from sqlalchemy import select
from sqlalchemy.orm import Session
from .core.security import hash_password
from .core.timeutil import utcnow
from .db import Base, SessionLocal, engine
from .domain.enums import FileType, Role
from .domain.file_validation import new_stored_name
from .models import (StudentRoster, Department, Program, ResearchCategory, ResearchWork, Revision, Role as RoleModel, StatusHistory, User,
                     FileRecord)
from .services import files_service, index_service
from .services.submission_service import _apply

DEMO_PASSWORD = "Drass2026"
ROLE_DESC = {
    "STUDENT": "Submits research and tracks status", "ADVISER": "Reviews assigned advisee submissions",
    "PANELIST": "Reviews assigned research as panel member", "DEAN": "Departmental approval stage",
    "LIBRARY_STAFF": "Browses repository and verifies metadata", "HEAD_LIBRARIAN": "Final archive approval",
    "ADMIN": "System administration", "EXTERNAL_USER": "Read-only access to approved research",
}
DEPTS = {"College of Information Technology": ["BS Information Technology", "BS Computer Science"],
         "College of Education": ["BS Secondary Education", "BS Elementary Education"],
         "College of Business": ["BS Business Administration", "BS Accountancy"],
         "College of Health Sciences": ["BS Nursing", "BS Midwifery"]}
CATEGORIES = ["Information Technology", "Education Technology", "Business", "Social Research", "Health", "Engineering", "Other"]
USERS = [  # username, role, full name, dept index (0=IT), student no
    ("admin", "ADMIN", "System Administrator", None, None), ("headlibrarian", "HEAD_LIBRARIAN", "Helena Reyes", None, None),
    ("librarian", "LIBRARY_STAFF", "Lorenzo Santos", None, None), ("dean", "DEAN", "Dr. Diana Villanueva", 0, None),
    ("adviser1", "ADVISER", "Prof. Adrian Cruz", 0, None), ("panelist1", "PANELIST", "Prof. Paolo Mendoza", 0, None),
    ("panelist2", "PANELIST", "Prof. Patricia Lim", 0, None), ("student1", "STUDENT", "Sofia Ramos", 0, "2022-0001"),
    ("student2", "STUDENT", "Miguel Garcia", 0, "2022-0002"), ("external1", "EXTERNAL_USER", "Erika Dela Cruz", None, None),
]
DEMO_WORKS = [  # title, abstract, keywords, year, program idx, category, authors
    ("Development of a Mobile Quiz Application for Improving Student Engagement in Science Education",
     "This study develops a mobile quiz application with instant feedback and leaderboards to raise student engagement and learning outcomes in junior high school science classes. Teachers reported improved participation and higher assessment scores after one semester.",
     ["mobile application", "quiz", "student engagement", "science education"], 2025, 4, "Education Technology", ["Andrea Bautista", "Carlo Tan"]),
    ("An AI Tutoring Chatbot for Mathematics Learning of Senior High School Students",
     "A chatbot tutor that explains mathematics problems step by step was built and tested with senior high school students. Learners using the chatbot showed improved problem solving and greater motivation to study independently.",
     ["chatbot", "tutoring", "mathematics", "learning"], 2025, 0, "Education Technology", ["Bianca Flores", "Jerome Aquino"]),
    ("Gamified Learning Management System to Increase Student Motivation in Online Classes",
     "The researchers designed a learning management system with badges, points and progress tracking to motivate students in online classes. Survey results show technology-based game elements improve student learning and attendance.",
     ["gamification", "learning management system", "motivation", "online learning"], 2024, 0, "Education Technology", ["Camille Ocampo", "Rico Dizon"]),
    ("Hospital Outpatient Queue Management System with SMS Notifications",
     "This capstone presents a queue management system for a community hospital outpatient department that reduces waiting time through ticketing and text message alerts for patients.",
     ["queue management", "hospital", "sms", "patient waiting time"], 2024, 0, "Health", ["Dennis Villar", "Ella Navarro"]),
    ("Dengue Case Monitoring and Mapping Web Application for Barangay Health Workers",
     "A web application that records dengue cases and maps hotspots helps barangay health workers plan cleanup drives and respond to outbreaks faster.",
     ["dengue", "disease monitoring", "mapping", "barangay health"], 2023, 0, "Health", ["Faith Mercado", "Gabriel Soriano"]),
    ("Inventory and Sales Monitoring System for Sari-Sari Stores",
     "The study builds a lightweight inventory and sales tracking system for small neighborhood stores to reduce stock-outs and improve daily profit visibility.",
     ["inventory", "sales monitoring", "small business", "retail"], 2024, 4, "Business", ["Hannah Pascual", "Ian Salazar"]),
    ("Factors Influencing E-Commerce Adoption Among Micro and Small Enterprises in Quezon City",
     "Using a survey of micro and small enterprise owners, this research examines trust, cost and digital skills as factors that influence e-commerce adoption.",
     ["e-commerce", "adoption", "small enterprises", "survey"], 2023, 4, "Business", ["Jasmine Cortez", "Kevin Uy"]),
    ("Social Media Use and Academic Well-Being of College Students",
     "This descriptive study examines how daily social media use relates to stress, sleep and academic performance among college students.",
     ["social media", "well-being", "college students", "academic performance"], 2025, 2, "Social Research", ["Lara Gomez", "Mark Estrada"]),
    ("Campus Network Intrusion Detection and Security Monitoring Dashboard",
     "A dashboard collects network logs and flags suspicious traffic on a campus network, helping administrators detect intrusions and respond to security incidents.",
     ["network security", "intrusion detection", "dashboard", "logs"], 2026, 1, "Information Technology", ["Nina Padilla", "Oscar Lopez"]),
    ("IoT-Based Flood Monitoring and Early Warning System for Riverside Communities",
     "Water level sensors connected to a microcontroller send readings to a web dashboard and issue alerts to residents when flood risk rises.",
     ["internet of things", "flood", "sensors", "early warning"], 2026, 0, "Engineering", ["Paula Rivera", "Quentin Abad"]),
    ("Solar-Powered Automated Irrigation System for Urban Vegetable Gardens",
     "An automated drip irrigation controller powered by a solar panel and soil moisture sensors reduces water use in urban community gardens.",
     ["solar power", "irrigation", "automation", "urban gardening"], 2024, 0, "Engineering", ["Rhea Castillo", "Samuel Ortega"]),
    ("Library Book Recommendation System Using Student Borrowing History",
     "A recommender suggests library books to students based on borrowing history and course enrollment to encourage reading and reduce time spent searching shelves.",
     ["recommendation system", "library", "borrowing history", "reading"], 2025, 0, "Information Technology", ["Tina Valdez", "Uriel Cabrera"]),
]


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(title: str, body: str, pages: int = 3) -> bytes:
    """Minimal valid multi-page PDF using only the standard library (synthetic demo manuscripts)."""
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            ("<< /Type /Pages /Kids [%s] /Count %d >>" % (" ".join(f"{4 + 2 * i} 0 R" for i in range(pages)), pages)).encode(),
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    for i in range(pages):
        lines = [f"{title[:90]}", f"Demonstration manuscript - page {i + 1} of {pages}", ""] + \
                textwrap.wrap(body * 3, 85)[:40]
        txt = "BT /F1 12 Tf 72 740 Td 16 TL " + " ".join(f"({_esc(l)}) Tj T*" for l in lines) + " ET"
        stream = txt.encode("latin-1", "replace")
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>".encode())
        objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for n, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def seed_core(db: Session) -> None:
    if db.scalar(select(RoleModel)) is not None:
        return
    roles = {r.value: RoleModel(role_name=r.value, description=ROLE_DESC[r.value]) for r in Role}
    db.add_all(roles.values())
    depts = []
    for dname, progs in DEPTS.items():
        d = Department(department_name=dname); db.add(d); db.flush(); depts.append(d)
        for p in progs:
            db.add(Program(department_id=d.department_id, program_name=p))
    db.add_all(ResearchCategory(category_name=c) for c in CATEGORIES)
    db.flush()
    pw = hash_password(DEMO_PASSWORD)
    for username, role, name, dept_i, sn in USERS:
        db.add(User(username=username, password_hash=pw, role_id=roles[role].role_id, full_name=name,
                    email=f"{username}@demo.drass.local", student_number=sn,
                    department_id=depts[dept_i].department_id if dept_i is not None else None))
    db.commit()


ROSTER = [("2022-0001", "Ramos", "Sofia"), ("2022-0002", "Garcia", "Miguel"), ("2023-0101", "Reyes", "Carla"),
          ("2023-0102", "Tan", "Daniel"), ("2023-0103", "Lim", "Erika"), ("2023-0104", "Santos", "Paolo")]


def seed_roster(db: Session) -> int:
    """Idempotent: adds missing demo roster rows (first three are claimed by the demo students/none)."""
    dept = db.scalar(select(Department).order_by(Department.department_id))
    have = set(db.scalars(select(StudentRoster.student_number)).all())
    n = 0
    for sn, last, first in ROSTER:
        if sn not in have:
            db.add(StudentRoster(student_number=sn, last_name=last, first_name=first, department_id=dept.department_id if dept else None)); n += 1
    db.commit()
    return n


def seed_demo(db: Session) -> int:
    if db.scalar(select(ResearchWork).where(ResearchWork.reference_no.like("DEMO-%"))) is not None:
        return 0
    files_service.ensure_dirs()
    programs = db.scalars(select(Program).order_by(Program.program_id)).all()
    cats = {c.category_name: c.category_id for c in db.scalars(select(ResearchCategory)).all()}
    adviser = db.scalar(select(User).where(User.username == "adviser1"))
    submitter = db.scalar(select(User).where(User.username == "student2"))   # demo records owned by student2 so student1 starts clean
    created = []
    for i, (title, abstract, kws, year, prog_i, cat, authors) in enumerate(DEMO_WORKS, 1):
        prog = programs[prog_i]
        w = ResearchWork(submitted_by=submitter.user_id, current_status="ARCHIVED", title=title, abstract="",
                         reference_no=f"DEMO-{i:03d}", submitted_at=utcnow(), archived_at=utcnow())
        db.add(w); db.flush()
        _apply(db, w, {"title": title, "abstract": abstract, "year": year, "program_id": prog.program_id,
                       "department_id": prog.department_id, "category_id": cats[cat], "adviser_id": adviser.user_id,
                       "authors": [{"name": a} for a in authors], "keywords": kws})
        rev = Revision(work_id=w.work_id, revision_number=1, submitted_by=submitter.user_id, change_notes="Seeded demo record")
        db.add(rev); db.flush()
        w.current_revision_id = rev.revision_id
        db.add(StatusHistory(work_id=w.work_id, from_status=None, to_status="ARCHIVED", reason="Seeded demo record"))
        data = make_pdf(title, abstract)
        stored = new_stored_name(".pdf")
        with open(files_service.dest_path(FileType.MANUSCRIPT, stored), "wb") as f:
            f.write(data)
        db.add(FileRecord(work_id=w.work_id, revision_id=rev.revision_id, file_type="MANUSCRIPT",
                          original_filename="manuscript.pdf", stored_filename=stored, storage_path=f"manuscripts/{stored}",
                          mime_type="application/pdf", size_bytes=len(data), sha256_checksum=hashlib.sha256(data).hexdigest(),
                          uploaded_by=submitter.user_id))
        created.append(w.work_id)
    db.commit()
    for wid in created:
        index_service.index_work(db, wid, None)
    return len(created)


def main() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_core(db)
        seed_roster(db)
        n = 0 if "--no-demo" in sys.argv else seed_demo(db)
    print(f"Seed complete. Demo research records created: {n}. See docs/DEMO_ACCOUNTS.md for logins.")


if __name__ == "__main__":
    main()
