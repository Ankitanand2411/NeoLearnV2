from fastapi import APIRouter
from app.services.persona_registry import get_all_personas

router = APIRouter(prefix="/personas", tags=["Personas"])


@router.get("")
async def list_personas():
    """
    Return the full persona registry — name, domain, era, teaching style.
    Used by the frontend to display mentor cards on the Learn page.
    """
    personas = get_all_personas()
    return {
        "personas": [
            {
                "id": p["id"],
                "name": p["name"],
                "domain": p["domain"],
                "era": p["era"],
                "teaching_style": p["teaching_style"],
            }
            for p in personas.values()
        ]
    }


@router.get("/{persona_id}")
async def get_persona_detail(persona_id: str):
    """Return full detail for a single persona."""
    from app.services.persona_registry import get_persona
    persona = get_persona(persona_id)
    if not persona:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Persona '{persona_id}' not found")
    return persona
