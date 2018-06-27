'''
Functions to work with ASEG-GDF format string
Refer to https://www.aseg.org.au/sites/default/files/pdf/ASEG-GDF2-REV4.pdf for further information

Created on 19 Jun. 2018

@author: u76345
'''

import re
import numpy as np
from collections import OrderedDict
from math import log10, ceil
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) # Logging level for this module


# Approximate maximum number of significant decimal figures for each signed datatype
SIG_FIGS = OrderedDict([('int8', 2), # 128
                        ('int16', 4), # 32768
                        ('int32', 10), # 2147483648 - should be 9, but made 10 because int64 is unsupported
                        ('int64', 19), # 9223372036854775808
                        # https://en.wikipedia.org/wiki/Floating-point_arithmetic#IEEE_754:_floating_point_in_modern_computers
                        ('float32', 7), # 7.2
                        ('float64', 20) # 15.9 - should be 16, but made 20 to support unrealistic precision specifications
                        ]
                       )

DTYPE_REDUCTION_LISTS = [['int64', 'int32', 'int16', 'int8'], # Integer dtypes
                         ['float64', 'float32'] # Floating point dtypes
                         ]
    
ASEG_DTYPE_CODE_MAPPING = {'int16': 'I',
                           'int32': 'I',
                           'int64': 'I',
                           'float32': 'F',
                           'float64': 'D',
                           'str': 'A'
                           }

def decode_aseg_gdf_format(aseg_gdf_format):
    '''
    Function to decode ASEG-GDF format string
    @param aseg_gdf_format: ASEG-GDF format string

    @return columns: Number of columns (i.e. 1 for 1D data, or read from format string for 2D data)
    @return aseg_dtype_code: ASEG-GDF data type character, e.g. "F" or "I"
    @return integer_digits: Number of integer digits read from format string
    @return fractional_digits: Number of fractional digits read from format string    
    '''
    if not aseg_gdf_format:
        raise BaseException('No ASEG-GDF format string to decode')  

    match = re.match('(\d+)*(\w)(\d+)\.*(\d+)*', aseg_gdf_format)
    
    if not match:
        raise BaseException('Invalid ASEG-GDF format string {}'.format(aseg_gdf_format))  
      
    columns = match.group(1) or 1
    aseg_dtype_code = match.group(2).upper()
    integer_digits = int(match.group(3))
    fractional_digits = int(match.group(4)) if match.group(4) is not None else 0
    
    logger.debug('aseg_gdf_format: {}, columns: {}, aseg_dtype_code: {}, integer_digits: {}, fractional_digits: {}'.format(aseg_gdf_format, 
                                                                                                                      columns, 
                                                                                                                      aseg_dtype_code, 
                                                                                                                      integer_digits, 
                                                                                                                      fractional_digits
                                                                                                                      )
                 ) 
    return columns, aseg_dtype_code, integer_digits, fractional_digits  

def aseg_gdf_format2dtype(aseg_gdf_format):
    '''
    Function to return Python data type string and other precision information from ASEG-GDF format string
    @param aseg_gdf_format: ASEG-GDF format string

    @return dtype: Data type string, e.g. int8 or float32
    @return columns: Number of columns (i.e. 1 for 1D data, or read from format string for 2D data)
    @return integer_digits: Number of integer digits read from format string
    @return fractional_digits: Number of fractional digits read from format string    
    '''
    columns, aseg_dtype_code, integer_digits, fractional_digits = decode_aseg_gdf_format(aseg_gdf_format)
    dtype = None # Initially unknown datatype
    
    # Determine type and size for required significant figures
    # Integer type - N.B: Only signed types available
    if aseg_dtype_code == 'I':
        assert not fractional_digits, 'Integer format cannot be defined with fractional digits'
        for test_dtype, sig_figs in SIG_FIGS.items():
            if test_dtype.startswith('int') and sig_figs >= integer_digits:
                dtype = test_dtype
                break
        assert dtype, 'Invalid integer length of {}'.format(integer_digits)     
    
    # Floating point type - use approximate sig. figs. to determine length
    elif aseg_dtype_code in ['D', 'E', 'F']: 
        for test_dtype, sig_figs in SIG_FIGS.items():
            if test_dtype.startswith('float') and sig_figs >= integer_digits + fractional_digits:
                dtype = test_dtype
                break
        assert dtype, 'Invalid floating point format of {}.{}'.format(integer_digits, fractional_digits)                                    
    
    if aseg_dtype_code == 'A':
        assert not fractional_digits, 'String format cannot be defined with fractional digits'
        dtype = str
        
    else:
        raise BaseException('Unhandled ASEG-GDF dtype code {}'.format(aseg_dtype_code))
    
    logger.debug('aseg_dtype_code: {}, columns: {}, integer_digits: {}, fractional_digits: {}'.format(dtype, 
                                                                                                 columns, 
                                                                                                 integer_digits, 
                                                                                                 fractional_digits
                                                                                                 )
                 ) 
    return dtype, columns, integer_digits, fractional_digits


def variable2aseg_gdf_format(array_variable, decimal_places=None):
    '''
    Function to return ASEG-GDF format string and other info from data array or netCDF array variable
    @param array_variable: data array or netCDF array variable
    @param decimal_places: Number of decimal places to respect, or None for value derived from datatype and values
    
    @return aseg_gdf_format: ASEG-GDF format string
    @return dtype: Data type string, e.g. int8 or float32
    @return columns: Number of columns (i.e. 1 for 1D data, or second dimension size for 2D data)
    @return integer_digits: Number of integer digits (derived from maximum value)
    @return fractional_digits: Number of fractional digits (derived from datatype sig. figs - integer_digits)
    @param python_format: Python Formatter string for fixed-width output
    '''
    if len(array_variable.shape) == 1: # 1D variable
        columns = 1
    elif len(array_variable.shape) == 2: # 2D variable
        columns = array_variable.shape[1]
    else:
        raise BaseException('Unable to handle arrays with dimensionality > 3')
        
    dtype = str(array_variable.dtype)
    data_array = array_variable[:]
    
    # Include fill value if required
    if type(data_array) == np.ma.core.MaskedArray:
        logger.debug('Array is masked. Including fill value.')
        data_array = data_array.data
            
    sig_figs = SIG_FIGS[dtype] + 1 # Look up approximate significant figures and add 1
    sign_width = 1 if np.nanmin(data_array) < 0 else 0
    integer_digits = ceil(log10(np.nanmax(np.abs(data_array)) + 1.0))
    
    aseg_dtype_code = ASEG_DTYPE_CODE_MAPPING.get(dtype)
    assert aseg_dtype_code, 'Unhandled dtype {}'.format(dtype)
    
    if aseg_dtype_code == 'I': # Integer
        fractional_digits = 0
        aseg_gdf_format = 'I{}'.format(integer_digits)
        python_format = '{' + ':{:d}.{:d}f'.format(sign_width+integer_digits, fractional_digits) + '}'
    elif aseg_dtype_code in ['F', 'D']: # Floating point
        # If array_variable is a netCDF variable with a "format" attribute, use stored format string to determine fractional_digits
        if decimal_places is not None:
            fractional_digits = min(decimal_places, sig_figs-integer_digits)
            logger.debug('fractional_digits set to {} from decimal_places {}'.format(fractional_digits, decimal_places))
        elif hasattr(array_variable, 'aseg_gdf_format'): 
            _columns, _aseg_dtype_code, _integer_digits, fractional_digits = decode_aseg_gdf_format(array_variable.aseg_gdf_format)
            fractional_digits = min(fractional_digits, sig_figs-integer_digits+1)
            logger.debug('fractional_digits set to {} from variable attribute aseg_gdf_format {}'.format(fractional_digits, array_variable.aseg_gdf_format))
        else: # No aseg_gdf_format variable attribute
            fractional_digits = sig_figs - integer_digits + 1
            logger.debug('fractional_digits set to {} from sig_figs {} and integer_digits {}'.format(fractional_digits, sig_figs, integer_digits))
            
        aseg_gdf_format = '{}{}.{}'.format(aseg_dtype_code, integer_digits, fractional_digits)
        python_format = '{' + ':{:d}.{:d}f'.format(sign_width+integer_digits+fractional_digits+1, fractional_digits) + '}' # Add 1 to width for decimal point
    elif aseg_dtype_code == 'A': # String
        #TODO: Finish implementing this properly
        if hasattr(array_variable, 'aseg_gdf_format'):
            _columns, _aseg_dtype_code, integer_digits, fractional_digits = decode_aseg_gdf_format(array_variable.aseg_gdf_format)
        else:
            # TODO: Remove hard-coded hack
            integer_digits = 40
            fractional_digits = 0
        python_format = '{' + ':{:d}s'.format(integer_digits) + '}'
    else:
        raise BaseException('Unhandled ASEG-GDF dtype code {}'.format(aseg_dtype_code))
    
    # Pre-pend column count to start of aseg_gdf_format
    if columns > 1:
        aseg_gdf_format = '{}{}'.format(columns, aseg_gdf_format)
        
    return aseg_gdf_format, dtype, columns, integer_digits, fractional_digits, python_format


def fix_field_precision(array_variable, current_dtype, fractional_digits, fill_value=None):
    '''
    Function to return revised ASEG-GDF format string and other info from data array or netCDF array variable
    after correcting datatype for excessive precision specification, or None if there is no precision change.
    Arrays are copied to smaller representations and then the difference with the original is checked to
    ensure that any difference is less than precision of the specified number of fractional digits.
    Note that fill_value is also considered but potentially modified only if data precision is changed
    @param array_variable: data array or netCDF array variable - assumed to be of dtype float64 for raw data
    @param current_dtype: Current data type string, e.g. int8 or float32
    @param fractional_digits: Number of fractional digits for precision checking
    @param fill_value: fill value or None
    
    Returns None if no precision change required.
    @return aseg_gdf_format: ASEG-GDF format string
    @return dtype: Data type string, e.g. int8 or float32
    @return columns: Number of columns (i.e. 1 for 1D data, or second dimension size for 2D data)
    @return integer_digits: Number of integer digits (derived from maximum value)
    @return fractional_digits: Number of fractional digits (derived from datatype sig. figs - integer_digits)
    @return python_format: Python Formatter string for fixed-width output
    @return fill_value: Potentially modified fill value
    '''
    logger.debug('array_variable: {}, current_dtype: {}, fractional_digits: {}'.format(array_variable, current_dtype, fractional_digits))
    
    for dtype_reduction_list in DTYPE_REDUCTION_LISTS:
        try:
            current_dtype_index = dtype_reduction_list.index(current_dtype)
            data_array = array_variable[:]
            
            # Include fill value if required
            if type(data_array) == np.ma.core.MaskedArray:
                logger.debug('Array is masked. Including fill value.')
                fill_value = data_array.fill_value # Use masked array fill value instead of any provided value
                no_data_mask = data_array.mask
                data_array = data_array.data # Include mask value
            if fill_value is not None:
                no_data_mask = (data_array == fill_value)
            
            # Try types from smallest to largest
            for smaller_dtype in dtype_reduction_list[:current_dtype_index:-1]:                
                smaller_array = data_array.astype(smaller_dtype)
                difference_array = data_array - smaller_array
                logger.debug('current_dtype: {}\nsmaller_dtype: {}\narray_variable\n{}\nsmaller_array\n{}\n\
difference_array\n{}\nfractional_digits: {}\ndifference count: {}\ndifference values: '.format(current_dtype, 
                                                                                               smaller_dtype, 
                                                                                               data_array, 
                                                                                               smaller_array, 
                                                                                               difference_array, 
                                                                                               fractional_digits, 
                                                                                               np.count_nonzero(difference_array >= pow(10, -fractional_digits)), 
                                                                                               difference_array[difference_array != 0]
                                                                                               )
                      )
                if np.count_nonzero(np.abs(difference_array) >= pow(10, -fractional_digits)):
                    # Differences found - try larger datatype
                    continue
                else:
                    aseg_gdf_format, dtype, columns, integer_digits, fractional_digits, python_format = variable2aseg_gdf_format(smaller_array, fractional_digits)

                    if fill_value is not None:
                        # Use reduced precision fill_value if available and unambiguous
                        if np.any(no_data_mask):
                            reduced_precision_fill_value = data_array[no_data_mask][0] 
                            
                            # Check for ambiguity introduced by reduced precision
                            if np.any(data_array[~no_data_mask] == reduced_precision_fill_value):
                                logger.debug('Reduced precision fill value of {} is ambiguous'.format(reduced_precision_fill_value))
                                continue
                            else:
                                fill_value = reduced_precision_fill_value
                        
                        # Try truncating fill_value to <integer_digits>.<fractional_digits> rather than rounding for neater output later on
                        try:
                            pattern = re.compile('(-?)\d*?(\d{0,' + '{}'.format(integer_digits) + '}\.\d{0,' + '{}'.format(fractional_digits) + '})')
                            search = re.search(pattern, str(fill_value))
                            truncated_fill_value = float(search.group(1)+search.group(2))
                            assert not np.any(data_array[~no_data_mask] == truncated_fill_value), 'Truncated fill value of {} is ambiguous'.format(truncated_fill_value)
                            fill_value = truncated_fill_value
                        except Exception as e:
                            logger.info('Unable to truncate fill value to {}: {}'.format(aseg_gdf_format, e))
                            
                    return aseg_gdf_format, dtype, columns, integer_digits, fractional_digits, python_format, fill_value

            
        except ValueError: # current_dtype not in dtype_reduction_list
            continue
   
