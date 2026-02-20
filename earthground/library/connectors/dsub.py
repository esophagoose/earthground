import earthground.components as cmp


class Dsub(cmp.Component):
    """DB9 D-sub connector (9-pin)"""

    def __init__(self, pin_count: int):
        super().__init__(refdes_prefix="J")
        self.name = f"DSub<{pin_count}>"
        self.description = f"D-sub connector, {pin_count} pins"
        self.manufacturer = "Generic"
        self.mpn = f"DSub<{pin_count}>"
        self.pin_count = pin_count
        pins = {i: str(i) for i in range(1, pin_count + 1)}
        pins.update({"M1": "M1", "M2": "M2"})
        self.pins = cmp.PinContainer.from_dict(pins, self)

    def print(self):
        def get_pin_name(index):
            pin = self.pins.by_index(index)
            connection = "<NC>"
            if self.parent and pin in self.parent.pin_to_net:
                connection = self.parent.pin_to_net[pin].name
            return f"{index}: {connection}"

        def pin_label(i):
            n = int(i + 1)
            return str(n) if n > 9 else f" {n}"

        top_row = [pin_label(i) for i in range((self.pin_count + 1) // 2)]
        bottom_row = [
            pin_label(i) for i in range((self.pin_count + 1) // 2, self.pin_count)
        ]
        print(f"{self.refdes} ({self.name})")
        print("  " + " ".join(top_row))
        print("┌" + "-" * (len(top_row) * 3 + 2) + "┐")
        print("| " + "".join([" • " for _ in range(len(top_row))]) + " |")
        print(" \ " + "".join([" • " for _ in range(len(bottom_row))]) + "  /")
        print("  ╰" + "-" * (len(bottom_row) * 3 + 1) + "╯")
        print("    " + " ".join(bottom_row))


if __name__ == "__main__":
    dsub = Dsub(15)
    dsub.print()
