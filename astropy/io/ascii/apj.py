# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""An extensible ASCII table reader and writer.

apj.py:
  Classes to read ApJ online table format

Heavily based on sextractor.py
"""


import re

from . import core
from . import fixedwidth



class ApJHeader(core.BaseHeader):
    """Read the header from an online-only ApJ table"""
    # ApJ tables have no commented lines but keeping here just in case
    comment = r'^\s*#\s*\S\D.*'

    def get_cols(self, lines):
        """
        Initialize the header Column objects from the table ``lines``
        for a ApJ table header. The ApJ header is specialized
        so that we just copy the entire BaseHeader get_cols routine and
        modify as needed.

        Parameters
        ----------
        lines : list
            List of table lines

        """
        # This assumes that the columns are listed in order, one per
        # line with a header comment string of the format:
        # " 1- 15  <format> <units> short description"
        columns = {}
        colnumber = 0
        lines_left = -1
        for data_start, line in enumerate(lines, 1):
            # this happens 2 lines before column definitions
            if line.split()[0] == 'Bytes':
                lines_left = 1
                continue
            # the line just before column definitions, if we already
            # found the line referenced above
            if lines_left > 0 and line[:5] == '-'*5:
                lines_left = 0
                continue
            # once we've already read the column definitions, if we
            # hit dashes again means header is over.
            if lines_left == 0 and line[:5] == '-'*5:
                break
            # ready to go
            if lines_left == 0:
                if line[8] != ' ':
                    msg = 'Each row is more than 999 bytes long; this is' \
                          ' not yet supported.'
                    raise NotImplementedError(msg)
                colrange = line[:8].split('-')
                colstart = int(colrange[0]) - 1
                # single-byte columns do not specify a start and end
                # but simply the column byte. In that case, the line
                # consequently has one fewer entry (controlled by `n`
                # below)
                if len(colrange) == 1:
                    colend = colstart + 1
                    n = 0
                else:
                    colend = int(colrange[1]) - 1
                    n = 1
                words = line.split()
                colunit = '1' if words[n+2] == '---' else words[n+2]
                colname = words[n+3]
                coldescr = ' '.join(words[n+4:])
                columns[colnumber] = \
                    (colname, colstart, colend, coldescr, colunit)
                colnumber += 1

            colnumbers = sorted(columns)
            self.names = []
            for n in colnumbers:
                self.names.append(columns[n][0])

        if not self.names:
            raise core.InconsistentTableError(
                'No column names found in ApJ header')

        self.cols = []
        for n in colnumbers:
            col = core.Column(name=columns[n][0])
            col.start = columns[n][1]
            col.end = columns[n][2]
            col.description = columns[n][3]
            col.unit = columns[n][4]
            self.cols.append(col)


class ApJ(core.BaseReader):
    """Read an ApJ online table.
       The Astrophysical Journal (ApJ) is a journal of the American
       Astronomical Society published by IOP sciences.
       http://iopscience.iop.org/journal/0004-637X

    Example::

      Title: The Atacama Cosmology Telescope: Dynamical Masses and Scaling 
             Relations for a Sample of Massive Sunyaev-Zel'dovich Effect 
             Selected Galaxy Clusters
      Authors: Sifon C., Menanteau F., Hasselfield M., Marriage T.A., Hughes J.P., 
               Barrientos L.F., Gonzalez J., Infante L., Addison G.E., Baker A.J., 
               Battaglia N., Bond J.R., Crichton D., Das S., Devlin M.J., Dunkley J.,
               Dunner R., Gralla M.B., Hajian A., Hilton M., Hincks A.D., 
               Kosowsky A.B., Marsden D., Moodley K., Niemack M.D., Nolta M.R., 
               Page L.A., Partridge B., Reese E.D., Sehgal N., Sievers J., 
               Spergel D.N., Staggs S.T., Thornton R.J., Trac H., Wollack E.J.
      Table: Spectroscopic members of the 16 ACT clusters
      ================================================================================
      Byte-by-byte Description of file: apj475645t8_mrt.txt
      --------------------------------------------------------------------------------
         Bytes Format Units    Label  Explanations
      --------------------------------------------------------------------------------
         1- 22 A22    ---      ID     Galaxy identifier (1)
        24- 25 I2     h        RAh    Hour of Right Ascension (J2000)
        27- 28 I2     min      RAm    Minute of Right Ascension (J2000)
        30- 33 F4.1   s        RAs    Second of Right Ascension (J2000)
            35 A1     ---      DE-    Sign of the Declination (J2000)
        36- 37 I2     deg      DEd    Degree of Declination (J2000)
        39- 40 I2     arcmin   DEm    Arcminute of Declination (J2000)
        42- 45 F4.1   arcsec   DEs    Arcsecond of Declination (J2000)
        47- 52 F6.3   mag      imag   The i band magnitude
        54- 60 F7.5   ---      z      Cross-correlation redshift (2)
        62- 68 F7.5   ---    e_z      Error in z (2)
        70- 74 F5.2   ---      rcc    Cross-correlation S/N; Tonry & Davis 1979 (2)
        76-114 A39    ---      MSF    Main Spectral Features
      --------------------------------------------------------------------------------
      Note (1): Based on the J2000.0 position of each galaxy and using the initials 
                of the first three authors of this paper to identify the catalog.
      Note (2): From the RVSAO package in IRAF.
      --------------------------------------------------------------------------------
      SMH J010257.7-491619.2 01 02 57.7 -49 16 19.2 19.135 0.87014 0.00030  3.39 Ca-II(K,H)
      SMH J010301.9-491618.8 01 03 01.9 -49 16 18.8 22.722 0.86890 0.00022  3.59 Ca-II(K,H);[OII]

    Note that column lengths are defined in the block prior to the data,
    and that while columns are delimited by spaces, there can also be spaces
    within columns.
    """
    _format_name = 'apj'
    _io_registry_can_write = False
    _description = 'ApJ online data format table'

    header_class = ApJHeader
    data_class = ApJData
    # do I need to modify this one?
    inputter_class = core.ContinuationLinesInputter

    def __init__(self, col_starts=None, col_ends=None, delimiter_pad=' ',
                 bookend=True):
        super().__init__()
        self.data.splitter.delimiter_pad = delimiter_pad
        self.data.splitter.bookend = bookend
        self.header.col_starts = col_starts
        self.header.col_ends = col_ends

    def read(self, table):
        """
        Read input data (file-like object, filename, list of strings, or
        single string) into a Table and return the result.
        """
        out = super().read(table)
        # remove the comments
        if 'comments' in out.meta:
            del out.meta['comments']
        return out

    def write(self, table):
        raise NotImplementedError
