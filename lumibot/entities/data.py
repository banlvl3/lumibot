import datetime
import logging

import pandas as pd

from lumibot import LUMIBOT_DEFAULT_PYTZ as DEFAULT_PYTZ
from lumibot.tools.helpers import to_datetime_aware

from .dataline import Dataline


class Data:
    """Input and manage Pandas dataframes for backtesting.

    Parameters
    ----------
    asset : Asset Object
        Asset object to which this data is attached.
    df : dataframe
        Pandas dataframe containing OHLCV etc trade data. Loaded by user
        from csv.
        Index is date and must be pandas datetime64.
        Columns are strictly ["open", "high", "low", "close", "volume"]
    date_start : Datetime or None
        Starting date for this data, if not provided then first date in
        the dataframe.
    date_end : Datetime or None
        Ending date for this data, if not provided then last date in
        the dataframe.
    trading_hours_start : datetime.time or None
        If not supplied, then default is 0001 hrs.
    trading_hours_end : datetime.time or None
        If not supplied, then default is 2359 hrs.
    timestep : str
        Either "minute" (default) or "day"
    columns : list of str
        For feeding in desired columns (not yet used).

    Attributes
    ----------
    asset : Asset Object
        Asset object to which this data is attached.
    sybmol : str
        The underlying or stock symbol as a string.
    df : dataframe
        Pandas dataframe containing OHLCV etc trade data. Loaded by user
        from csv.
        Index is date and must be pandas datetime64.
        Columns are strictly ["open", "high", "low", "close", "volume"]
    date_start : Datetime or None
        Starting date for this data, if not provided then first date in
        the dataframe.
    date_end : Datetime or None
        Ending date for this data, if not provided then last date in
        the dataframe.
    trading_hours_start : datetime.time or None
        If not supplied, then default is 0001 hrs.
    trading_hours_end : datetime.time or None
        If not supplied, then default is 2359 hrs.
    timestep : str
        Either "minute" (default) or "day"
    columns : list of str
        For feeding in desired columns (not yet used).
    datalines : dict
        Keys are column names like `datetime` or `close`, values are
        numpy arrays.
    iter_index : Pandas Series
        Datetime in the index, range count in values. Used to retrieve
        the current df iteration for this data and datetime.

    Methods
    -------
    set_times
        Sets the start and end time for the data.
    repair_times_and_fill
        After all time series merged, adjust the local dataframe to reindex and fill nan's.
    columns
        Adjust date and column names to lower case.
    set_date_format
        Ensure datetime in local datetime64 format.
    set_dates
        Set start and end dates.
    trim_data
        Trim the dataframe to match the desired backtesting dates.

    to_datalines
        Create numpy datalines from existing date index and columns.
    get_iter_count
        Returns the current index number (len) given a date.
    check_data (wrapper)
        Validates if the provided date, length, timeshift, and timestep
        will return data. Runs function if data, returns None if no data.
    get_last_price
        Gets the last price from the current date.
    _get_bars_dict
        Returns bars in the form of a dict.
    get_bars
        Returns bars in the form of a dataframe.
    """

    MIN_TIMESTEP = "minute"
    TIMESTEP_MAPPING = [
        {"timestep": "day", "representations": ["1D", "day"]},
        {"timestep": "minute", "representations": ["1M", "minute"]},
    ]

    def __init__(
        self,
        asset,
        df,
        date_start=None,
        date_end=None,
        trading_hours_start=datetime.time(0, 0),
        trading_hours_end=datetime.time(23, 59),
        timestep="minute",
        columns=None,
    ):
        self.asset = asset
        self.symbol = self.asset.symbol

        self.timestep = timestep
        self.df = self.columns(df)
        self.df = self.set_date_format(self.df)

        self.trading_hours_start, self.trading_hours_end = self.set_times(
            trading_hours_start, trading_hours_end
        )
        self.date_start, self.date_end = self.set_dates(date_start, date_end)

        self.df = self.trim_data(
            self.df,
            self.date_start,
            self.date_end,
            self.trading_hours_start,
            self.trading_hours_end,
        )
        self.datetime_start = self.df.index[0]
        self.datetime_end = self.df.index[-1]

    def set_times(self, trading_hours_start, trading_hours_end):
        """Set the start and end times for the data. The default is 0001 hrs to 2359 hrs.

        Parameters
        ----------
        trading_hours_start : datetime.time
            The start time of the trading hours.

        trading_hours_end : datetime.time
            The end time of the trading hours.

        Returns
        -------
        trading_hours_start : datetime.time
            The start time of the trading hours.

        trading_hours_end : datetime.time
            The end time of the trading hours.
        """
        # Set the trading hours start and end times.
        if self.timestep == "minute":
            ts = trading_hours_start
            te = trading_hours_end
        else:
            ts = datetime.time(0, 0)
            te = datetime.time(23, 59, 59, 999999)
        return ts, te

    def columns(self, df):
        # Select columns to use, change to lower case, rename `date` if necessary.
        df.columns = [
            col.lower()
            if col.lower() in ["open", "high", "low", "close", "volume"]
            else col
            for col in df.columns
        ]

        return df

    def set_date_format(self, df):
        df.index.name = "datetime"
        df.index = pd.to_datetime(df.index)
        if not df.index.tzinfo:
            df.index = df.index.tz_localize(DEFAULT_PYTZ)
        elif df.index.tzinfo != DEFAULT_PYTZ:
            df.index = df.index.tz_convert(DEFAULT_PYTZ)
        return df

    def set_dates(self, date_start, date_end):
        # Set the start and end dates of the data.
        for dt in [date_start, date_end]:
            if dt and not isinstance(dt, datetime.datetime):
                raise TypeError(
                    f"Start and End dates must be entries as full datetimes. {dt} "
                    f"was entered"
                )

        if not date_start:
            date_start = self.df.index[0]
        if not date_end:
            date_end = self.df.index[-1]

        date_start = to_datetime_aware(date_start)
        date_end = to_datetime_aware(date_end)

        date_start = date_start.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date_end.replace(hour=23, minute=59, second=59, microsecond=999999)

        return (
            date_start,
            date_end,
        )

    def trim_data(
        self, df, date_start, date_end, trading_hours_start, trading_hours_end
    ):
        # Trim the dataframe to match the desired backtesting dates.

        df = df.loc[(df.index > date_start) & (df.index < date_end), :]
        if self.timestep == "minute":
            df = df.between_time(trading_hours_start, trading_hours_end)
        if df.empty:
            raise ValueError(
                f"When attempting to load a dataframe for {self.asset}, "
                f"and empty dataframe was returned. This is likely due "
                f"to your backtesting start and end dates not being "
                f"within the start and end dates of the data provided. "
                f"\nPlease check that your at least one of your start "
                f"or end dates for backtesting is within the range of "
                f"your start and end dates for your data. "
            )
        return df

    def repair_times_and_fill(self, idx):
        # Trim the global index so that it is within the local data.
        idx = idx[(idx >= self.datetime_start) & (idx <= self.datetime_end)]

        # After all time series merged, adjust the local dataframe to reindex and fill nan's.
        df = self.df.reindex(idx)
        df.loc[df["volume"].isna(), "volume"] = 0
        df.loc[:, ~df.columns.isin(["open", "high", "low"])] = df.loc[
            :, ~df.columns.isin(["open", "high", "low"])
        ].ffill()
        for col in ["open", "high", "low"]:
            df.loc[df[col].isna(), col] = df.loc[df[col].isna(), "close"]

        self.df = df

        iter_index = pd.Series(df.index)
        self.iter_index = pd.Series(iter_index.index, index=iter_index)

        self.datalines = dict()
        self.to_datalines()

    def to_datalines(self):
        self.datalines.update(
            {
                "datetime": Dataline(
                    self.asset,
                    "datetime",
                    self.df.index.to_numpy(),
                    self.df.index.dtype,
                )
            }
        )
        setattr(self, "datetime", self.datalines["datetime"].dataline)

        for column in self.df.columns:
            self.datalines.update(
                {
                    column: Dataline(
                        self.asset,
                        column,
                        self.df[column].to_numpy(),
                        self.df[column].dtype,
                    )
                }
            )
            setattr(self, column, self.datalines[column].dataline)

    def get_iter_count(self, dt):
        # Return the index location for a given datetime.
        return self.iter_index[dt]

    def check_data(func):
        # Validates if the provided date, length, timeshift, and timestep
        # will return data. Runs function if data, returns None if no data.
        def checker(self, *args, **kwargs):
            dt = args[0]
            # Check if the iter date is outside of this data's date range.
            if dt < self.datetime_start or dt > self.datetime_end:
                return None

            data_index = (
                self.iter_index[dt]
                + 1
                - kwargs.get("length", 1)
                - kwargs.get("timeshift", 0)
            )
            is_data = data_index >= 0
            if not is_data:
                return None

            res = func(self, *args, **kwargs)
            # print(f"Results last price: {res}")
            return res

        return checker

    @check_data
    def is_tradable(self, dt, length=1, timestep="minute", timeshift=0):
        """Returns True if the data is tradeable.

        Parameters
        ----------
        dt : datetime.datetime
            The datetime to check for tradeability.
        length : int
            The number of periods to check for tradeability.
        timestep : str
            The frequency of the data to check for tradeability.
        timeshift : int
            The number of periods to shift the data.

        Returns
        -------
        bool
        """
        # Return true if data is available for trading. None if not.
        return True

    @check_data
    def get_last_price(self, dt, length=1, timeshift=0):
        """Returns the last price of the data.

        Parameters
        ----------
        dt : datetime.datetime
            The datetime to get the last price.
        length : int
            The number of periods to get the last price.
        timestep : str
            The frequency of the data to get the last price.
        timeshift : int
            The number of periods to shift the data.

        Returns
        -------
        float
        """
        # Get the last close price.
        return self.datalines["close"].dataline[self.get_iter_count(dt)]

    @check_data
    def _get_bars_dict(self, dt, length=1, timestep=None, timeshift=0):
        """Returns a dictionary of the data.

        Parameters
        ----------
        dt : datetime.datetime
            The datetime to get the data.
        length : int
            The number of periods to get the data.
        timestep : str
            The frequency of the data to get the data.
        timeshift : int
            The number of periods to shift the data.

        Returns
        -------
        dict

        """
        # Get bars.
        end_row = self.get_iter_count(dt) + 1 - timeshift
        start_row = end_row - length
        if start_row < 0:
            start_row = 0

        df_dict = {}
        for dl_name, dl in self.datalines.items():
            df_dict[dl_name] = dl.dataline[start_row:end_row]

        return df_dict

    def get_bars(self, dt, length=1, timestep=MIN_TIMESTEP, timeshift=0):
        """Returns a dictionary of the data.

        Parameters
        ----------
        dt : datetime.datetime
            The datetime to get the data.
        length : int
            The number of periods to get the data.
        timestep : str
            The frequency of the data to get the data.
        timeshift : int
            The number of periods to shift the data.

        Returns
        -------
        pandas.DataFrame

        """
        df_dict = self._get_bars_dict(
            dt, length=length, timestep=self.timestep, timeshift=timeshift
        )
        if df_dict is not None:
            return pd.DataFrame(df_dict).set_index("datetime")
        return None
