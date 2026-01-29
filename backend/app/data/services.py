"""
Medical services catalog.
Gender-specific services with pricing.
"""

from typing import Dict, List
from app.models.schemas import MedicalService


# Male-specific medical services
MALE_SERVICES: List[MedicalService] = [
    MedicalService(
        id="m1",
        name="General Health Checkup",
        price=500.0,
        description="Comprehensive health screening including blood tests and vitals"
    ),
    MedicalService(
        id="m2",
        name="Cardiac Screening",
        price=800.0,
        description="ECG, stress test, and heart health evaluation"
    ),
    MedicalService(
        id="m3",
        name="Prostate Examination",
        price=600.0,
        description="PSA test and prostate health screening"
    ),
    MedicalService(
        id="m4",
        name="Diabetes Screening",
        price=400.0,
        description="Fasting glucose, HbA1c, and related tests"
    ),
    MedicalService(
        id="m5",
        name="Full Body Scan",
        price=1500.0,
        description="Complete CT scan and MRI imaging"
    ),
    MedicalService(
        id="m6",
        name="Liver Function Test",
        price=350.0,
        description="Complete liver panel and hepatitis screening"
    ),
]

# Female-specific medical services
FEMALE_SERVICES: List[MedicalService] = [
    MedicalService(
        id="f1",
        name="General Health Checkup",
        price=500.0,
        description="Comprehensive health screening including blood tests and vitals"
    ),
    MedicalService(
        id="f2",
        name="Mammography",
        price=700.0,
        description="Breast cancer screening and imaging"
    ),
    MedicalService(
        id="f3",
        name="Gynecological Exam",
        price=650.0,
        description="Pap smear, pelvic exam, and reproductive health check"
    ),
    MedicalService(
        id="f4",
        name="Bone Density Scan",
        price=550.0,
        description="DEXA scan for osteoporosis screening"
    ),
    MedicalService(
        id="f5",
        name="Thyroid Panel",
        price=450.0,
        description="Complete thyroid function tests"
    ),
    MedicalService(
        id="f6",
        name="Full Body Scan",
        price=1500.0,
        description="Complete CT scan and MRI imaging"
    ),
    MedicalService(
        id="f7",
        name="Prenatal Checkup",
        price=800.0,
        description="Complete pregnancy health evaluation"
    ),
]


def get_services_by_gender(gender: str) -> List[MedicalService]:
    """Get services based on gender."""
    if gender.lower() == "male":
        return MALE_SERVICES
    elif gender.lower() == "female":
        return FEMALE_SERVICES
    else:
        raise ValueError(f"Invalid gender: {gender}")


def get_service_by_id(service_id: str, gender: str) -> MedicalService:
    """Get a specific service by ID and gender."""
    services = get_services_by_gender(gender)
    for service in services:
        if service.id == service_id:
            return service
    raise ValueError(f"Service not found: {service_id}")


def get_services_by_ids(service_ids: List[str], gender: str) -> List[MedicalService]:
    """Get multiple services by IDs."""
    services = get_services_by_gender(gender)
    service_map = {s.id: s for s in services}
    result = []
    for sid in service_ids:
        if sid in service_map:
            result.append(service_map[sid])
        else:
            raise ValueError(f"Service not found: {sid}")
    return result


def calculate_base_price(services: List[MedicalService]) -> float:
    """Calculate total base price of services."""
    return sum(s.price for s in services)
