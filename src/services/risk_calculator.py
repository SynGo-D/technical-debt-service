class RiskCalculator:

    WEIGHTS = {
        "LOW": 1,
        "MEDIUM": 2,
        "HIGH": 3,
        "CRITICAL": 4
    }

    def calculate(
        self,
        risks: list[str]
    ) -> str:

        if not risks:
            return "LOW"

        highest = max(
            self.WEIGHTS.get(
                risk.upper(),
                1
            )
            for risk in risks
        )

        for name, value in self.WEIGHTS.items():

            if value == highest:
                return name

        return "LOW"