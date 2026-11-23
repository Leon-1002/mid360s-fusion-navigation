#include "rmc.h"
#include <stdio.h>

static int leap(unsigned year)
{
    return year % 4 == 0 && (year % 100 != 0 || year % 400 == 0);
}

int make_bench_rmc(uint32_t epoch, char *out, size_t capacity)
{
    static const unsigned month_days[12] = {31,28,31,30,31,30,31,31,30,31,30,31};
    unsigned days = epoch / 86400u, seconds = epoch % 86400u;
    unsigned year = 1970, month = 0, n, i, checksum = 0;
    char body[96];
    int length, total;
    while (days >= (n = 365u + (unsigned)leap(year))) { days -= n; ++year; }
    while (days >= (n = month_days[month] + (month == 1 && leap(year)))) { days -= n; ++month; }
    /* V and N deliberately mean no valid GNSS position/fix. Time is synthetic. */
    length = snprintf(body, sizeof(body), "GPRMC,%02u%02u%02u.00,V,,,,,,,%02u%02u%02u,,,N",
                      seconds / 3600u, seconds / 60u % 60u, seconds % 60u,
                      days + 1u, month + 1u, year % 100u);
    if (length < 0 || (size_t)length >= sizeof(body)) return -1;
    for (i = 0; i < (unsigned)length; ++i) checksum ^= (unsigned char)body[i];
    total = snprintf(out, capacity, "$%s*%02X\r\n", body, checksum);
    if (total < 0 || (size_t)total >= capacity) return -1;
    return total;
}
