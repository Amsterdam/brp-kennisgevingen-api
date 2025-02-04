def is_valid_bsn(value: str) -> bool:
    if not isinstance(value, str):
        return False
    bsn_len = len(value)
    if bsn_len != 9 or not value.isdigit():
        return False

    # Loop trough each of the individual numbers, starting at the first.
    # Multiply each one by (9 - index) and add it to the total.
    total = 0
    for index in range(8):
        t = value[index]
        total += int(t) * (9 - index)
    last_number = int(value[8])

    # Validate if the remainder of the total divided by 11 is equal to the last number in the BSN
    return total % 11 == last_number
