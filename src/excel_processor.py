import re
import pandas as pd
from descriptors import VerifyInputFile
from logger import Logger
from custom_exceptions import ASHRAE140ProcessingError
from src.data_cleanser import DataCleanser


class SectionType:
    """
    Identify Section Type based on input file name
    """
    def __get__(self, obj, owner):
        section_type = obj._section_type
        return section_type

    def __set__(self, obj, value):
        if re.match(r'.*results5-2a.*', str(value.name), re.IGNORECASE):
            obj._section_type = '5-2A'
        elif re.match(r'.*results5-2b.*', str(value.name), re.IGNORECASE):
            obj._section_type = '5-2B'
        else:
            obj.logger.error('Error: The file name ({}) did not match formatting guidelines or '
                             'the referenced section at the beginning of the name is not supported'
                             .format(str(value.name)))
        return


class SetDataSources:
    """
    Set the data extraction instructions.  Currently, this is a very simple descriptor, but it is created for
    future versions where data source location may change.

    data_sources formatting:
        0 - tab
        1 - start row
        2 - columns
        3 - number of rows to parse
        4 - dictionary of additional arguments to pd.read_excel
    """
    def __get__(self, obj, owner):
        data_sources = obj._data_sources
        return data_sources

    def __set__(self, obj, value):
        if isinstance(value, dict) and value:
            obj._data_sources = value
        else:
            if obj.section_type == '5-2A':
                obj._data_sources = {
                    'identifying_information': ('YourData', 60, 'B:C', 3, {'header': None}),
                    'conditioned_zone_loads_non_free_float': ('YourData', 68, 'B:L', 46),
                    'solar_radiation_annual_incident': ('YourData', 153, 'B:C', 5),
                    'solar_radiation_unshaded_annual_transmitted': ('YourData', 161, 'B:C', 4),
                    'solar_radiation_shaded_annual_transmitted': ('YourData', 168, 'B:C', 2),
                    'sky_temperature_output': ('YourData', 176, 'B:K', 1),
                    'annual_hourly_zone_temperature_bin_data': ('YourData', 328, 'B:C', 149),
                    'free_float_case_zone_temperatures': ('YourData', 128, 'B:K', 7),
                    'monthly_conditioned_zone_loads': ('YourData', 188, 'B:R', 12)
                }
            elif obj.section_type == '5-2B':
                obj._data_sources = {
                    'identifying_information': ('YourData', 4, 'E:I', 4, {'header': None}),
                    'steady_state_cases': ('YourData', 57, 'D:H', 6, {'header': None})
                }
            else:
                obj.logger.error('Error: Section ({}) is not currently supported'.format(obj.section_type))
        return


class SetProcessingFunctions:
    """
    Set the functions to perform for processing.
    """
    def __get__(self, obj, owner):
        processing_functions = obj._processing_functions
        return processing_functions

    def __set__(self, obj, value):
        if value == '5-2A':
            obj._processing_functions = {
                'identifying_information': obj._extract_identifying_information_2a(),
                'conditioned_zone_loads_non_free_float': obj._extract_conditioned_zone_loads_non_free_float(),
                'solar_radiation_annual_incident': obj._extract_solar_radiation_annual_incident(),
                'solar_radiation_unshaded_annual_transmitted': obj._extract_solar_radiation_unshaded_annual_transmitted(),
                'solar_radiation_shaded_annual_transmitted': obj._extract_solar_radiation_shaded_annual_transmitted(),
                'sky_temperature_output': obj._extract_sky_temperature_output(),
                'hourly_annual_zone_temperature_bin_data': obj._extract_hourly_annual_zone_temperature_bin_data(),
                'free_float_case_zone_temperatures': obj._extract_free_float_case_zone_temperatures(),
                'monthly_conditioned_zone_loads': obj._extract_monthly_conditioned_zone_loads()}
        elif value == '5-2B':
            obj._processing_functions = {
                'identifying_information': obj._extract_identifying_information_2b(),
                'steady_state_cases': obj._extract_steady_state_cases()}
        else:
            obj.logger.error('Error: Section ({}) is not currently supported'.format(obj.section_type))
        return


class ExcelProcessor(Logger):
    """
    Extract, Transform, and Load operations for Excel input data

    :param file_location: location of file to be processed
    :param data_sources (Optional): data extraction instructions.
    """

    file_location = VerifyInputFile()
    section_type = SectionType()
    data_sources = SetDataSources()
    processing_functions = SetProcessingFunctions()

    def __init__(
            self,
            file_location,
            data_sources=None,
            logger_level="WARNING",
            logger_name="console_only_logger"):
        super().__init__(logger_level=logger_level, logger_name=logger_name)
        self.file_location = file_location
        self.section_type = self.file_location
        self.data_sources = data_sources
        self.processing_functions = self.section_type
        self.test_data = {}
        self.software_name = None
        self.software_version = None
        self.software_release_date = None
        return

    def __repr__(self):
        rep = 'ExcelProcessor(' \
              'file_location=' + str(self.file_location) + \
              ')'
        return rep

    def _get_data(self, region_name) -> pd.DataFrame:
        """
        Retrieve section of data and return it as a pandas dataframe

        :param region_name: Named section of data in the data_sources class object.
        :return: Section of excel file converted to dataframe
        """
        try:
            data_source = self.data_sources[region_name]
        except KeyError:
            raise ASHRAE140ProcessingError('Data extraction instructions for Identifying Information section '
                                           'was not found')
        data_tab, skip_rows, excel_cols, n_rows, kwargs = [*list(data_source) + [{}] * 5][:5]
        df = pd.read_excel(
            self.file_location,
            sheet_name=data_tab,
            skiprows=skip_rows,
            usecols=excel_cols,
            nrows=n_rows,
            **kwargs)
        # todo_140: Write simple verifications that data loaded
        return df

    # Section 5-2A data
    def _extract_identifying_information_2a(self):
        """
        Retrieve information data from section 2A submittal and store it as class attributes.

        :return: Class attributes identifying software program.
        """
        df = self._get_data('identifying_information')
        if not re.match(r'^Software.*', df.iloc[0, 0]):
            self.logger.error('Software name information not found')
            self.software_name = None
        else:
            self.software_name = df.iloc[0, 1]
        if not re.match(r'^Version.*', df.iloc[1, 0]):
            self.logger.error('Software version information not found')
            self.software_version = None
        else:
            self.software_version = df.iloc[1, 1]
        if not re.match(r'^Date.*', df.iloc[2, 0]):
            self.logger.error('Software release date information not found')
            self.software_release_date = None
        else:
            self.software_release_date = df.iloc[2, 1]
        data_d = {
            'software_name': self.software_name,
            'software_version': self.software_version,
            'software_release_date': str(self.software_release_date)
        }
        return data_d

    def _extract_conditioned_zone_loads_non_free_float(self) -> dict:
        """
        Retrieve and format data from the
        Conditioned Zone Loads (Non-Free-Float Test Cases) table

        :return: dictionary to be merged into main testing output dictionary
        """
        df = self._get_data('conditioned_zone_loads_non_free_float')
        # format and verify dataframe
        df.columns = ['case', 'annual_heating_MWh', 'annual_cooling_MWh', 'peak_heating_kW', 'peak_heating_month',
                      'peak_heating_day', 'peak_heating_hour', 'peak_cooling_kW', 'peak_cooling_month',
                      'peak_cooling_day', 'peak_cooling_hour']
        df['case'] = df['case'].astype(str)
        dc = DataCleanser(df)
        df = dc.cleanse_conditioned_zone_loads_non_free_float()
        # format cleansed dataframe into dictionary
        data_d = {}
        for idx, row in df.iterrows():
            case_number = row[0]
            row_obj = df.iloc[idx, 1:].to_dict()
            data_d.update({
                str(case_number): row_obj})
        return data_d

    def _extract_solar_radiation_annual_incident(self) -> dict:
        """
        Retrieve and format data from the Solar Radiation ANNUAL INCIDENT (Total Direct-Beam and Diffuse) section

        :return: dictionary to be merged into main testing output dictionary
        """
        df = self._get_data('solar_radiation_annual_incident')
        df.columns = ['Surface', 'kWh/m2']
        dc = DataCleanser(df)
        df = dc.cleanse_solar_radiation_annual()
        data_d = {'600': {'Surface': {}}}
        for idx, row in df.iterrows():
            data_d['600']['Surface'].update({
                str(row['Surface']): {'kWh/m2': row['kWh/m2']}})
        return data_d

    def _extract_solar_radiation_unshaded_annual_transmitted(self) -> dict:
        """
        Retrieve and format data from the Solar Radiation UNSHADED ANNUAL TRANSMITTED
        (Total Direct-Beam and Diffuse) section

        :return: dictionary to be merged into main testing output dictionary
        """
        df = self._get_data('solar_radiation_unshaded_annual_transmitted')
        df.columns = ['Case/Surface', 'kWh/m2']
        df[['Case', 'Surface']] = df['Case/Surface'].str.split(pat='/', expand=True)
        df = df.drop(columns=['Case/Surface', ])
        dc = DataCleanser(df)
        df = dc.cleanse_solar_radiation_annual(case_column='Case')
        data_d = {}
        for idx, row in df.iterrows():
            data_d.update(
                {
                    row['Case']: {
                        'Surface': {
                            row['Surface']: {
                                'kWh/m2': row['kWh/m2']}}}})
        return data_d

    def _extract_solar_radiation_shaded_annual_transmitted(self):
        """
        Retrieve and format data from the Solar Radiation SHADED ANNUAL TRANSMITTED
        (Total Direct-Beam and Diffuse) section

        :return: dictionary to be merged into main testing output dictionary
        """
        df = self._get_data('solar_radiation_shaded_annual_transmitted')
        df.columns = ['Case/Surface', 'kWh/m2']
        df[['Case', 'Surface']] = df['Case/Surface'].str.split(pat='/', expand=True)
        df = df.drop(columns=['Case/Surface', ])
        dc = DataCleanser(df)
        df = dc.cleanse_solar_radiation_annual(case_column='Case')
        data_d = {}
        for idx, row in df.iterrows():
            data_d.update(
                {
                    row['Case']: {
                        'Surface': {
                            row['Surface']: {
                                'kWh/m2': row['kWh/m2']}}}})
        return data_d

    def _extract_sky_temperature_output(self) -> dict:
        """
        Retrieve and format data from the Sky Temperature Output table

        :return: dictionary to be merged into main testing output dictionary
        """
        df = self._get_data('sky_temperature_output')
        df.columns = ['case', 'Ann. Hourly Average C', 'Minimum C', 'Minimum Month', 'Minimum Day', 'Minimum Hour',
                      'Maximum C', 'Maximum Month', 'Maximum Day', 'Maximum Hour']
        dc = DataCleanser(df)
        df = dc.cleanse_sky_temperature_output()
        data_d = {'600': {}}
        for idx, row in df.iterrows():
            data_d['600'].update({'Average': {'C': row['Ann. Hourly Average C']}})
            data_d['600'].update({'Minimum': {
                'C': row['Minimum C'],
                'Month': row['Minimum Month'],
                'Hour': row['Minimum Hour']}})
            data_d['600'].update({'Maximum': {
                'C': row['Maximum C'],
                'Month': row['Maximum Month'],
                'Hour': row['Maximum Hour']
            }})
        return data_d

    def _extract_hourly_annual_zone_temperature_bin_data(self) -> dict:
        """
        Retrieve and format data from the Hourly Annual Zone Temperature Bin Data table

        :return: dictionary to be merged into main testing output dictionary
        """
        df = self._get_data('annual_hourly_zone_temperature_bin_data')
        df.columns = ['temperature_bin_c', 'number_of_hours']
        data_d = {'900FF': {'temperature_bin_c': {}}}
        for idx, row in df.iterrows():
            data_d['900FF']['temperature_bin_c'].update(
                {int(row['temperature_bin_c']): {'number_of_hours': int(row['number_of_hours'])}})
        return data_d

    def _extract_free_float_case_zone_temperatures(self):
        """
        Retrieve and format data from the Free Float Case Zone Temperature Table (5-2A)
        :return:  dictionary to be merged into main testing output dictionary
        """
        df = self._get_data('free_float_case_zone_temperatures')
        df.columns = ['case', 'average_temperature', 'minimum_temperature', 'minimum_month', 'minimum_day', 'minimum_hour',
                      'maximum_temperature', 'maximum_month', 'maximum_day', 'maximum_hour']
        dc = DataCleanser(df)
        df = dc.cleanse_free_float_case_zone_temperatures()
        data_d = {}
        for idx, row in df.iterrows():
            case_number = row[0]
            row_obj = df.iloc[idx, 1:].to_dict()
            data_d.update({
                str(case_number): row_obj})
        return data_d

    def _extract_monthly_conditioned_zone_loads(self):
        """
        Retrieve and format data from the Monthly Conditioned Zone Loads Table
        :return:  dictionary to be merged into main testing output dictionary
        """
        df = self._get_data('monthly_conditioned_zone_loads')
        df_columns = ['month', 'total_heating_kwh', 'total_cooling_kwh', 'peak_heating_kw', 'peak_heating_day',
                      'peak_heating_hour', 'peak_cooling_kw', 'peak_cooling_day', 'peak_cooling_hour']
        df_600 = df.iloc[:, range(9)].copy()
        df_600.columns = df_columns
        df_600['case'] = '600'
        df_900 = df.iloc[:, [0, ] + list(range(9, 17))].copy()
        df_900.columns = df_columns
        df_900['case'] = '900'
        dc_600 = DataCleanser(df_600)
        dc_900 = DataCleanser(df_900)
        df_600 = dc_600.cleanse_monthly_conditioned_loads()
        df_900 = dc_900.cleanse_monthly_conditioned_loads()
        df = pd.concat([df_600, df_900], ignore_index=True)
        data_d = {}
        for idx, row in df.iterrows():
            case_number = str(row['case'])
            col_idx = [i for i, j in enumerate(df.columns) if j not in ['case', 'index', 'month']]
            row_obj = df.iloc[idx, col_idx].to_dict()
            if not data_d.get(case_number):
                data_d[case_number] = {}
            data_d[case_number].update({
                row['month']: row_obj})
        return data_d

    # Section 5-2B data
    def _extract_identifying_information_2b(self):
        """
        Retrieve information data from section 2A submittal and store it as class attributes.

        :return: Class attributes identifying software program.
        """
        df = self._get_data('identifying_information')
        self.software_name = df.iloc[2, 4]
        self.software_version = str(df.iloc[0, 0]).replace(str(df.iloc[2, 4]), '').strip()
        self.software_release_date = str(df.iloc[1, 4])
        data_d = {
            'program_name_and_version': df.iloc[0, 0],
            'program_version_release_date': str(df.iloc[1, 4]),
            'program_name_short': df.iloc[2, 4],
            'results_submittal_date': str(df.iloc[3, 4])}
        return data_d

    def _extract_steady_state_cases(self):
        """
        Retrieve and format data from the Steady State table (5-2B)

        :return: dictionary to be merged into main testing output dictionary
        """
        df = self._get_data('steady_state_cases')
        df.columns = ['cases', 'qfloor', 'qzone', 'Tzone', 'tsim']
        data_d = {}
        for idx, row in df.iterrows():
            data_d[row['cases']] = {
                'qfloor': row['qfloor'],
                'qzone': row['qzone'],
                'Tzone': row['Tzone'],
                'tsim': row['tsim']}
        return data_d

    def run(self):
        """
        Perform operations to convert Excel file into dictionary of dataframes.

        :return: json object of input data
        """
        self.test_data.update(self.processing_functions)
        return self
