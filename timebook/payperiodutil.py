# Copyright (c) 2011-2012 Adam Coddington
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
from datetime import datetime, timedelta

from dateutil import relativedelta
from dateutil import rrule


class PayPeriodUtil(object):
    def __init__(self, db, begin_period=None, end_period=None,
            weekdays_rule=None, hours_per_day=8):
        self.db = db
        self.begin_period = begin_period
        self.end_period = end_period
        self.weekdays_rule = weekdays_rule
        self.hours_per_day = hours_per_day
        if not self.begin_period:
            self.begin_period = datetime.now() - relativedelta.relativedelta(
                    day=31, months=1, hour=0, minute=0,
                    second=0, weekday=rrule.FR(-2)
                ) + timedelta(days=1)
        if not self.end_period:
            self.end_period = datetime.now()
            self.real_end_period = datetime.now(
                    ) + relativedelta.relativedelta(
                            day=31, weekday=rrule.FR(-2)
                        )
        if(self.end_period > self.real_end_period):
            self.begin_period = datetime.now(
                    ) - relativedelta.relativedelta(
                            day=31, months=0, hour=0, minute=0,
                            second=0, weekday=rrule.FR(-2)
                        ) + timedelta(days=1)
            self.real_end_period = datetime.now(
                    ) + relativedelta.relativedelta(
                            day=31, months=1, weekday=rrule.FR(-2)
                        )
        if not self.weekdays_rule:
            self.weekdays_rule = rrule.rrule(
                    rrule.DAILY, byweekday=(
                        rrule.MO, rrule.TU, rrule.WE, rrule.TH, rrule.FR,
                    ), dtstart=self.begin_period
                )

    def get_hours_details(self):
        all_weekdays = self.weekdays_rule.between(
                self.begin_period,
                self.end_period
            )
        expected_hours = self.hours_per_day * len(all_weekdays)
        unpaid = 0
        vacation = 0
        holiday = 0

        for day in all_weekdays:
            if(self.is_holiday(day)):
                expected_hours = expected_hours - self.hours_per_day
                holiday = holiday + self.hours_per_day
            elif(self.is_unpaid(day)):
                expected_hours = expected_hours - self.hours_per_day
                unpaid = unpaid + self.hours_per_day
            elif(self.is_vacation(day)):
                expected_hours = expected_hours - self.hours_per_day
                vacation = vacation + self.hours_per_day
        total_hours = self.count_hours_after(
                self.begin_period,
                self.end_period
            )

        out_time = datetime.now() + timedelta(
                hours=(expected_hours - total_hours)
            )

        outgoing = {
                    'expected': expected_hours,
                    'actual': total_hours,
                    'vacation': vacation,
                    'unpaid': unpaid,
                    'holiday': holiday,
                    'out_time': out_time,
                    'begin_period': self.begin_period,
                    'end_period': self.real_end_period,
                }
        outgoing['balance'] = outgoing['actual'] - outgoing['expected']
        return outgoing

    def is_unpaid(self, date_to_check):
        dx = date_to_check
        self.db.execute("""
            SELECT * FROM unpaid
            WHERE year = ? AND month = ? AND day = ?
            """, (dx.year, dx.month, dx.day,))
        if(self.db.fetchone()):
            return True
        else:
            return False

    def is_vacation(self, date_to_check):
        dx = date_to_check
        self.db.execute("""
            SELECT * FROM vacation
            WHERE year = ? AND month = ? AND day = ?
            """, (dx.year, dx.month, dx.day,))
        if(self.db.fetchone()):
            return True
        else:
            return False

    def is_holiday(self, date_to_check):
        dx = date_to_check
        self.db.execute("""
            SELECT * FROM holidays
            WHERE year = ? AND month = ? AND day = ?
            """, (dx.year, dx.month, dx.day,))
        if(self.db.fetchone()):
            return True
        else:
            return False

    def count_hours_for_day(self, begin_time):
        self.db.execute("""
            SELECT SUM(
                COALESCE(end_time, STRFTIME('%s', 'now'))
                - start_time)
            FROM entry
            WHERE
                start_time >= STRFTIME('%s', ?, 'utc')
                AND
                start_time <= STRFTIME('%s', ?, 'utc', '1 day')
                AND
                sheet = 'default'
            """, (
                begin_time.strftime("%Y-%m-%d"),
                begin_time.strftime("%Y-%m-%d"),
                ))
        result = self.db.fetchone()
        if(result[0]):
            total_hours = float(result[0]) / 60 / 60
        else:
            total_hours = 0
        return total_hours

    def count_hours_after(self, begin_time, end_time):
        self.db.execute("""
            SELECT SUM(
                COALESCE(end_time, STRFTIME('%s', 'now'))
                - start_time)
            FROM entry
            WHERE
                start_time >= STRFTIME('%s', ?, 'utc')
                AND
                (
                    end_time <= STRFTIME('%s', ?, 'utc', '1 day')
                    OR
                    end_time is null
                )
                AND sheet = 'default'
            """, (
                begin_time.strftime("%Y-%m-%d"),
                end_time.strftime("%Y-%m-%d")
                ))
        result = self.db.fetchone()
        if(result[0]):
            total_hours = float(result[0]) / 60 / 60
        else:
            total_hours = 0
        return total_hours
