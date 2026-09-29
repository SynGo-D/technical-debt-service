class CostCalculator:

    def __init__(self, hourly_rate: float):

        self.hourly_rate = hourly_rate

    def calculate(
        self,
        total_minutes: int
    ) -> float:

        hours = total_minutes / 60

        return round(
            hours * self.hourly_rate,
            2
        )