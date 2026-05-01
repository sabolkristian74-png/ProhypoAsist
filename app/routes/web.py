from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, validator
from calculations.hypo import (
    calculate_monthly_payment,
    generate_amortization_schedule,
    optimize_insurance_initial
)
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
router = APIRouter()


class CalcInput(BaseModel):
    loan_amount: float = Field(..., gt=0)
    annual_rate: float = Field(..., ge=0)
    years: int = Field(..., gt=0)
    first_payment: date
    insurance_sum: float = Field(..., ge=0)
    insurance_years: int = Field(..., ge=0)
    increase_pct: float = Field(0.0, ge=0)

    @validator("first_payment")
    def valid_date(cls, v):
        if v is None:
            raise ValueError("Invalid date")
        return v


@router.get("/")
async def index(request: Request):
    # Render template without passing the Request object into the Jinja globals
    # to avoid Jinja caching errors caused by unhashable request in globals.
    tpl = templates.env.get_template("index.html")
    content = tpl.render({})
    return HTMLResponse(content)


@router.post("/api/calculate")
async def calculate(payload: CalcInput):
    # compute monthly payment and schedule
    monthly = calculate_monthly_payment(payload.loan_amount, payload.annual_rate, payload.years)
    schedule = generate_amortization_schedule(
        payload.loan_amount,
        payload.annual_rate,
        payload.years,
        payload.first_payment,
        payload.insurance_sum,
        payload.insurance_years,
        payload.increase_pct,
    )

    optimized = None
    try:
        optimized = optimize_insurance_initial(schedule, payload.insurance_years)
    except Exception:
        optimized = None

    total_interest = sum(r["interest"] for r in schedule)
    total_paid = sum(r["payment"] for r in schedule)

    return JSONResponse({
        "monthly_payment": monthly,
        "schedule": schedule,
        "optimized": optimized,
        "total_interest": total_interest,
        "total_paid": total_paid,
        "n_payments": payload.years * 12,
    })
