from typing import List, Dict, Optional, Tuple
from datetime import date, timedelta
from dataclasses import dataclass
import math


def _add_months(src_date: date, months: int) -> date:
    year = src_date.year + (src_date.month - 1 + months) // 12
    month = (src_date.month - 1 + months) % 12 + 1
    day = min(src_date.day, 28)
    return date(year, month, day)


def calculate_monthly_payment(P: float, annual_rate: float, years: int) -> float:
    """Calculate annuity monthly payment.

    Args:
        P: principal (loan amount)
        annual_rate: annual rate in percent (e.g., 3.5)
        years: number of years

    Returns:
        Monthly payment amount (float)
    """
    if years <= 0:
        raise ValueError("years must be > 0")
    n = years * 12
    r = annual_rate / 100.0 / 12.0
    if r == 0:
        return P / n
    denom = (1 + r) ** n - 1
    if denom == 0:
        return P / n
    M = P * (r * (1 + r) ** n) / denom
    return M


def generate_amortization_schedule(
    P: float,
    annual_rate: float,
    years: int,
    first_payment: date,
    insurance_initial: float,
    insurance_years: int,
    increase_pct: float = 0.0,
    constant_insurance: float = 0.0,
) -> List[Dict]:
    """Generate amortization schedule with insurance progression.

    Returns list of dicts for each month with keys:
    date, payment, interest, principal, balance, insurance, difference
    """
    n = years * 12
    M = calculate_monthly_payment(P, annual_rate, years)
    r = annual_rate / 100.0 / 12.0

    # apply optional increase percentage to initial insurance
    insurance_initial = insurance_initial * (1 + increase_pct / 100.0)

    schedule: List[Dict] = []
    balance = P
    insurance_months = max(0, insurance_years * 12)

    for m in range(n):
        interest = balance * r
        principal = M - interest
        if principal > balance:
            principal = balance
            payment = balance + interest
        else:
            payment = M

        balance = max(0.0, balance - principal)

        # insurance decreases linearly to 0 over insurance_months
        if insurance_months == 0:
            base_insurance = 0.0
        else:
            factor = max(0.0, 1.0 - (m / insurance_months))
            base_insurance = insurance_initial * factor

        # add constant insurance (flat amount) to the base insurance
        const_ins = float(constant_insurance or 0.0)
        insurance_total = base_insurance + const_ins

        diff = insurance_total - balance

        schedule.append(
            {
                "month": m + 1,
                "date": _add_months(first_payment, m).isoformat(),
                "payment": round(payment, 2),
                "interest": round(interest, 2),
                "principal": round(principal, 2),
                "balance": round(balance, 2),
                "insurance": round(base_insurance, 2),
                "constant_insurance": round(const_ins, 2),
                "insurance_total": round(insurance_total, 2),
                "difference": round(diff, 2),
            }
        )

        if balance <= 0:
            break

    return schedule


def optimize_insurance_initial(schedule: List[Dict], insurance_years: int) -> Dict[str, Optional[float]]:
    """Compute minimal initial insurance so insurance never falls below balance.

    If insurance period shorter than loan period, return suggestion to extend period.
    """
    if not schedule:
        return {"required_initial": None, "note": "Empty schedule"}

    insurance_months = insurance_years * 12
    n = len(schedule)

    # if insurance period is zero or shorter than loan term, it may be impossible
    if insurance_months == 0:
        return {"required_initial": None, "note": "Insurance duration is zero; cannot cover loan."}

    if insurance_months < n:
        # It's impossible to cover beyond insurance months unless insurance years increased
        return {
            "required_initial": None,
            "note": "Insurance duration shorter than loan term; consider extending insurance years",
        }

    required = 0.0
    for idx, row in enumerate(schedule):
        m = idx
        denom = max(1e-12, 1.0 - (m / insurance_months))
        candidate = row["balance"] / denom
        if candidate > required:
            required = candidate

    return {"required_initial": round(required, 2), "note": None}
