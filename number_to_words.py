def number_to_words_bdt(amount):
    if amount == 0:
        return "Zero Taka Only"

    ones = [
        "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
        "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
        "Seventeen", "Eighteen", "Nineteen"
    ]
    tens = [
        "", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy",
        "Eighty", "Ninety"
    ]

    def two_digit(n):
        if n < 20:
            return ones[n]
        return (ones[n % 10] if n % 10 else "") if n % 10 else tens[n // 10]

    def three_digit(n):
        parts = []
        if n >= 100:
            parts.append(ones[n // 100] + " Hundred")
            n %= 100
        if n >= 10:
            t = n // 10
            o = n % 10
            if t == 1:
                parts.append(ones[n])
            else:
                s = tens[t]
                if o:
                    s += " " + ones[o]
                parts.append(s)
        elif n > 0:
            parts.append(ones[n])
        return " ".join(parts)

    def convert(n):
        if n == 0:
            return ""
        parts = []
        if n >= 10000000:
            parts.append(three_digit(n // 10000000) + " Crore")
            n %= 10000000
        if n >= 100000:
            parts.append(three_digit(n // 100000) + " Lakh")
            n %= 100000
        if n >= 1000:
            parts.append(three_digit(n // 1000) + " Thousand")
            n %= 1000
        if n > 0:
            parts.append(three_digit(n))
        return " ".join(parts)

    integer_part = int(amount)
    result = convert(integer_part) + " Taka"
    return result + " Only"
