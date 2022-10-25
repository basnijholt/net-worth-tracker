from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class Snapshot:
    date: datetime
    n_months: int
    n_years: int
    net_worth: float
    net_worth_inflation_corrected: float
    save_per_month: float
    monthly_spending: float
    investment_income: float
    fire: bool
    age: float | None = None


def compound(
    average_saving_daily: float,
    monthly_spending: float,
    continue_n_years_after_retirement: int | None = 10,
    n_months: int | None = None,
    date_of_birth: int | None = None,
    yearly_pct_raise: int = 5,
    percent_rule: int = 4,
    inflation: float = 2,
    start_with: int = 200_000,
    interest_per_year: int = 7,
    # TODO: either use continue_n_years_after_retirement or until_age
) -> list[Snapshot]:
    pct_per_month = interest_per_year / 12
    save_per_month = average_saving_daily * 365 / 12

    lst = []
    total = start_with
    now = datetime.now()
    months_fire = 0
    date = datetime.now()
    for i in range(12 * 100):
        date += timedelta(days=365.25 / 12)
        if i % 12 == 0:
            save_per_month *= 1 + yearly_pct_raise / 100
        monthly_spending *= (1 + (inflation / 100)) ** (1 / 12)
        total = total * (1 + pct_per_month / 100) + save_per_month
        net_worth_inflation_corrected = total * (1 - inflation / 100) ** (i / 12)
        investment_income = total * (percent_rule / 100) / 12
        financially_free = investment_income > monthly_spending
        age = (date - date_of_birth).days / 365 if date_of_birth else None
        ss = Snapshot(
            date=now + timedelta(days=365.25 / 12 * i),
            n_months=i,
            n_years=i / 12,
            net_worth=total,
            net_worth_inflation_corrected=net_worth_inflation_corrected,
            save_per_month=save_per_month,
            monthly_spending=monthly_spending,
            investment_income=investment_income,
            fire=financially_free,
            age=age,
        )
        lst.append(ss)
        if financially_free:
            months_fire += 1
        if n_months is not None and i > n_months:
            break
        if (
            continue_n_years_after_retirement is not None
            and months_fire > 12 * continue_n_years_after_retirement
        ):
            break
    return lst


def cost_in_early_retirement(
    extra: float | int,
    average_saving_daily: float,
    monthly_spending: float,
    n_months: int | None = None,
    date_of_birth: int | None = None,
    yearly_pct_raise: int = 5,
    percent_rule: int = 4,
    inflation: float = 2,
    start_with: int = 200_000,
    interest_per_year: int = 7,
    verbose: bool = False,
) -> float:
    defaults = dict(
        average_saving_daily=average_saving_daily,
        monthly_spending=monthly_spending,
        n_months=n_months,
        date_of_birth=date_of_birth,
        yearly_pct_raise=yearly_pct_raise,
        percent_rule=percent_rule,
        inflation=inflation,
        start_with=start_with,
        interest_per_year=interest_per_year,
        continue_n_years_after_retirement=0,
    )
    frugal = compound(**defaults)
    kw = dict(defaults, start_with=defaults["start_with"] + extra)
    spend_it = compound(**kw)
    n_years = frugal[-1].n_years - spend_it[-1].n_years
    if verbose:
        print(f"Extra {extra} will last {n_years} years or {n_years * 12} months")
    return n_years
