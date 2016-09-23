import ujson as json
import luigi
import pandas as pd

from .BaseCapaldiAlg import BaseCapaldiAlg

import capaldi.etl as etl
import capaldi.checks as checks

from capaldi.algs.opencpu_support import dictified_json
from capaldi.algs.opencpu_support import opencpu_url_fmt
from capaldi.algs.opencpu_support import request_with_retries
from capaldi.algs.opencpu_support import r_ts_fmt


class GiantOakARIMA(BaseCapaldiAlg):
    """
    Run GO's version of the ARIMA algorithm on the supplied time series data.
    """
    hdf_out_key = luigi.Parameter(default='arima')

    def requires(self):
        cur_df = etl.CountsPerTPDataFrameCSV(self.working_dir, self.time_col)

        return {'file': cur_df,
                'error_checks': {
                    'too_few_buckets': checks.TooFewBuckets(
                        self.working_dir,
                        cur_df,
                        self.time_col),
                    'too_many_empties': checks.TooManyEmpties(
                        self.working_dir,
                        cur_df,
                        self.time_col)
                  }
                }

    def run(self):
        for error_key in self.requires()['error_checks']:
            jsn = json.loads(open(self.requires()[error_key]).read())
            if not jsn['result']:
                self.write_result(jsn)
                return

        with self.input()['file'].open('r') as infile:
            df = pd.read_csv(infile, parse_dates=['date_col'])

        url = opencpu_url_fmt('library',  # 'github', 'giantoak',
                              'goarima',
                              'R',
                              'arima_all',
                              'json')
        params = {'x': r_ts_fmt(df.count_col.tolist())}

        r = request_with_retries([url, params])

        if not r.ok:
            result_dict = {'error': r.txt}

        else:
            result_dict = dictified_json(
                r.json(),
                col_to_df_map={'df': ['ub', 'lb', 'resid']})

            result_dict['p_value'] = result_dict['p.value']
            del result_dict['p.value']

            result_dict['df']['dates'] = df.date_col

        self.write_result_to_hdf5(self.time_col, result_dict)

