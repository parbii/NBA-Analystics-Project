"""
US Federal Income Tax Calculator (2024 tax year)
Supports Single, Married Filing Jointly, and Head of Household filing statuses.
"""

# 2024 Federal Tax Brackets
TAX_BRACKETS = {
    "single": [
        (11600, 0.10),
        (47150, 0.12),
        (100525, 0.22),
        (191950, 0.24),
        (243725, 0.32),
        (609350, 0.35),
        (float("inf"), 0.37),
    ],
    "married_jointly": [
        (23200, 0.10),
        (94300, 0.12),
        (201050, 0.22),
        (383900, 0.24),
        (487450, 0.32),
        (731200, 0.35),
        (float("inf"), 0.37),
    ],
    "head_of_household": [
        (16550, 0.10),
        (63100, 0.12),
        (100500, 0.22),
        (191950, 0.24),
        (243700, 0.32),
        (609350, 0.35),
        (float("inf"), 0.37),
    ],
}

# 2024 Standard Deductions
STANDARD_DEDUCTIONS = {
    "single": 14600,
    "married_jointly": 29200,
    "head_of_household": 21900,
}

FILING_STATUS_LABELS = {
    "single": "Single",
    "married_jointly": "Married Filing Jointly",
    "head_of_household": "Head of Household",
}


def calculate_tax(taxable_income: float, filing_status: str) -> tuple[float, list[dict]]:
    """Calculate federal tax owed using progressive brackets."""
    brackets = TAX_BRACKETS[filing_status]
    tax = 0.0
    prev_limit = 0.0
    breakdown = []

    for limit, rate in brackets:
        if taxable_income <= prev_limit:
            break
        taxable_in_bracket = min(taxable_income, limit) - prev_limit
        tax_in_bracket = taxable_in_bracket * rate
        breakdown.append({
            "bracket": f"${prev_limit:,.0f} – {'∞' if limit == float('inf') else f'${limit:,.0f}'}",
            "rate": f"{rate:.0%}",
            "taxable": taxable_in_bracket,
            "tax": tax_in_bracket,
        })
        tax += tax_in_bracket
        prev_limit = limit

    return tax, breakdown


def run_calculator():
    print("\n=== US Federal Income Tax Calculator (2024) ===\n")

    # Filing status
    print("Filing Status:")
    print("  1. Single")
    print("  2. Married Filing Jointly")
    print("  3. Head of Household")
    choice = input("\nSelect (1-3): ").strip()
    status_map = {"1": "single", "2": "married_jointly", "3": "head_of_household"}
    if choice not in status_map:
        print("Invalid choice.")
        return
    filing_status = status_map[choice]

    # Gross income
    try:
        gross_income = float(input("Gross Annual Income ($): ").replace(",", ""))
    except ValueError:
        print("Invalid income amount.")
        return

    # Deductions
    standard = STANDARD_DEDUCTIONS[filing_status]
    print(f"\nStandard deduction for {FILING_STATUS_LABELS[filing_status]}: ${standard:,.0f}")
    use_standard = input("Use standard deduction? (y/n): ").strip().lower()

    if use_standard == "n":
        try:
            deduction = float(input("Enter itemized deduction amount ($): ").replace(",", ""))
        except ValueError:
            print("Invalid deduction amount.")
            return
    else:
        deduction = standard

    # Other adjustments
    try:
        other_deductions = float(input("Other adjustments/deductions (e.g. 401k, HSA) ($) [0 if none]: ").replace(",", "") or "0")
    except ValueError:
        other_deductions = 0.0

    taxable_income = max(0, gross_income - deduction - other_deductions)

    # Calculate
    federal_tax, breakdown = calculate_tax(taxable_income, filing_status)

    # FICA (Social Security + Medicare) — applies to earned income
    social_security = min(gross_income, 168600) * 0.062  # 6.2% up to wage base
    medicare = gross_income * 0.0145
    additional_medicare = max(0, gross_income - 200000) * 0.009  # 0.9% over $200k
    fica_total = social_security + medicare + additional_medicare

    total_tax = federal_tax + fica_total
    effective_rate = (federal_tax / gross_income * 100) if gross_income > 0 else 0
    take_home = gross_income - total_tax

    # Output
    print(f"\n{'='*50}")
    print(f"  TAX SUMMARY — {FILING_STATUS_LABELS[filing_status]}")
    print(f"{'='*50}")
    print(f"  Gross Income:          ${gross_income:>12,.2f}")
    print(f"  Deduction:            -${deduction:>12,.2f}")
    print(f"  Other Adjustments:    -${other_deductions:>12,.2f}")
    print(f"  Taxable Income:        ${taxable_income:>12,.2f}")
    print(f"\n  --- Federal Income Tax Bracket Breakdown ---")
    for b in breakdown:
        if b["taxable"] > 0:
            print(f"  {b['bracket']:>30}  @ {b['rate']}  →  ${b['tax']:,.2f}")
    print(f"\n  Federal Income Tax:    ${federal_tax:>12,.2f}")
    print(f"  Social Security:       ${social_security:>12,.2f}")
    print(f"  Medicare:              ${medicare + additional_medicare:>12,.2f}")
    print(f"  {'─'*38}")
    print(f"  Total Tax:             ${total_tax:>12,.2f}")
    print(f"  Effective Fed Rate:    {effective_rate:>11.2f}%")
    print(f"  Est. Take-Home Pay:    ${take_home:>12,.2f}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    run_calculator()
