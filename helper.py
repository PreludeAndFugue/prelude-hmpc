'''Helper functions and constants that are used in more than one module.'''

# competition status
OPEN = 0
SCORING = 1
COMPLETED = 2
# the total number of extra photos that can be uploaded
MAX_EXTRA_PHOTO = 80

MONTHS = {
    1: 'January',
    2: 'February',
    3: 'March',
    4: 'April',
    5: 'May',
    6: 'June',
    7: 'July',
    8: 'August',
    9: 'September',
    10: 'October',
    11: 'November',
    12: 'December'
}


def ordinal(n):
    '''Return ordinal number string from input integer.'''
    if 10 <= n % 100 < 20:
        return str(n) + 'th'
    else:
        return str(n) + {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, "th")
