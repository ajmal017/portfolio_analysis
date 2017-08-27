#!/usr/bin/env python
#
# Author  : Vikas Chouhan (presentisgood@gmail.com)
# License : GPLv2

import urllib, urllib2, json
import datetime
import pandas
import argparse
import copy
import time
import sys
import smtplib
import re
import os
import math
import contextlib, warnings
from   email.mime.multipart import MIMEMultipart
from   email.mime.text import MIMEText
from   email.mime.application import MIMEApplication
import matplotlib
from   matplotlib.finance import candlestick2_ohlc, volume_overlay
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.dates as mdates
import datetime as datetime
import numpy as np

# Switch matplotlib backend
matplotlib.pyplot.switch_backend('agg')

##############################################################
# Glb ds
sock = "bcbf3d08f70aaf07b860dc2f481beee5/1473605026"
res_tbl = {
              "1m"     : 1,
              "5m"     : 5,
              "15m"    : 15,
              "30m"    : 30,
              "1h"     : 60,
              "2h"     : 120,
              "4h"     : 240,
              "5h"     : 300,
              "1D"     : "D",
              "1W"     : "W",
              "1M"     : "M",
          }
intr_dy = [ "1m", "5m", "15m", "30m", "1h" ]

########################################################
# For EMAIL
def send_email(user, pwd, recipient, body='', subject="Sent from sim_stk_ind.py", attachments=[]):
    gmail_user = user
    gmail_pwd = pwd
    FROM = user
    TO = recipient if type(recipient) is list else [recipient]
    SUBJECT = subject
    TEXT = body

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = user
    msg['To']      = recipient
    msg.attach(MIMEText(TEXT, 'plain'))

    # Add all attachments 
    for a_this in attachments:
        with open(a_this,'rb') as fp:
            att = MIMEApplication(fp.read())
            att.add_header('Content-Disposition', 'attachment', filename=a_this)
            msg.attach(att)
        # endwith
    # endfor
    
    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.ehlo()
        #server.starttls()
        server.login(gmail_user, gmail_pwd)
        server.sendmail(FROM, TO, msg.as_string())
        server.close()
        print "Mail sent to {} at {}".format(recipient, datetime.datetime.now())
    except:
        print "Failed to send the mail !!"
# enddef

###############################################################
# Helper functions for Investing.com access
def g_sock():
    urlt = g_burlb()
    with contextlib.closing(urllib2.urlopen(urlt)) as s:
        return '/'.join(re.search('carrier=(\w+)&time=(\d+)&', s.read()).groups())
    # endwith
    assert(False)
# enddef

def g_burlb():
    return "http://tvc4.forexpros.com"
def g_burl(soc_idf):
    return g_burlb() + "/{}/1/1/8/history?".format(soc_idf)
def g_bsurl(soc_idf):
    return g_burlb() + "/{}/1/1/8/symbols?".format(soc_idf)

def strdate_to_unixdate(str_date):
    return int(time.mktime(datetime.datetime.strptime(str_date, '%d/%m/%Y').timetuple()))
# enddef

def unixdate_now():
    return int(time.mktime(datetime.datetime.now().timetuple()))
# enddef
def strdate_now():
    return datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S")

def scan_security_by_symbol(sym):
    this_url = g_bsurl(sock) + "symbol={}".format(sym)

    #print "{} : Fetching {}".format(strdate_now(), this_url)
    response = urllib.urlopen(this_url)
    j_data   = json.loads(response.read())
    if not bool(j_data):
        print "{} : Not able to fetch. Returned data = {}".format(strdate_now(), j_data)
        sys.exit(-1)
    else:
        return j_data["description"]
    # endif
# enddef

def fetch_data(sym, resl, t_from=None, sym_name=None):
    # Scan for the security with symbol 'sym'. Get it's name.
    # This acts as second level check
    if sym_name == None:
        sym_name = scan_security_by_symbol(sym)
    # endif
    #print 'Security with sym_name={} found with description={}'.format(sym, sym_name)

    if t_from == None:
        t_from = strdate_to_unixdate("01/01/1992")
    # endif
    ftch_tout = 5
    t_indx    = 0

    # Assert resolution check
    assert(resl in res_tbl.keys())
    

    while t_indx < ftch_tout:
        t_to     = unixdate_now()
        this_url = g_burl(sock) + "symbol={}&resolution={}&from={}&to={}".format(sym, res_tbl[resl], t_from, t_to)

        #print "{} : Fetching {}".format(strdate_now(), this_url)
        response = urllib.urlopen(this_url)
        j_data   = json.loads(response.read())
        if not bool(j_data):
            print "{} : Not able to fetch. Returned data = {}".format(strdate_now(), j_data)
        else:
            break
        # endif
        t_indx   = t_indx + 1
    # endwhile

    if (t_indx >= ftch_tout):
        msg_err = "{} : Retries exceeded !!".format(strdate_now())
        print msg_err
        # Alert user by sending mail
        #send_email(gm_sender, gm_passwd, gm_receiver, "Unable to fetch sym info. Killing process !!")
        # Exit
        return None, msg_err
    # endif

    # Get basic pb_frame
    def g_pdbase(j_data):
        x_alt_a  = range(0, len(j_data['c']))
        t_data   = [ datetime.datetime.fromtimestamp(int(x)) for x in j_data['t'] ]
        d_frame  = pandas.DataFrame(index=x_alt_a)
    
        d_frame['c'] = j_data['c']
        d_frame['o'] = j_data['o']
        d_frame['h'] = j_data['h']
        d_frame['l'] = j_data['l']
        d_frame['t'] = t_data
        d_frame['T'] = j_data['t']

        if 'v' in j_data:
            d_frame['v']  = j_data['v']
        # endif
        if 'vo' in j_data:
            d_frame['vo'] = j_data['vo']
        # endif
    
        return d_frame
    # enddef

    #print "{} : Fetched data. done !!".format(strdate_now())
    return g_pdbase(j_data), sym_name
# enddef

####################################################
# PLOTTING FUNCTIONS
#
def gen_candlestick(d_frame, mode='c', period_list=[], title='', file_name=None, plot_period=None, time_out=None):
    d_frame_c_c = d_frame.copy()

    # Slice the frame which needs to be plotted
    d_frame_c = d_frame_c_c[-plot_period:].copy()

    # Get date list and rmean function
    xdate     = [datetime.datetime.fromtimestamp(t) for t in d_frame_c['T']]
    rmean     = g_rmean_f(type='e')

    def close_event():
        plt.close()
    # endif

    def mydate(x,pos):
        try:
            return xdate[int(x)]
        except IndexError:
            return ''
        # endtry
    # enddef

    # Pre-processing
    fig = plt.figure()
    if time_out:
        timer = fig.canvas.new_timer(interval=time_out*1000)  # time_out is in seconds
        timer.add_callback(close_event)
    # endif
    ax  = fig.add_subplot(111)
    plt.xticks(rotation = 45)
    plt.xlabel("Date")
    plt.ylabel("Price")
    plt.title(title)

    # Plot candlestick
    candlestick2_ohlc(ax, d_frame_c['o'], d_frame_c['h'], d_frame_c['l'], d_frame_c['c'], width=0.6)
    ## Plot mas
    for period_this in period_list:
        label = 'ema_' + str(period_this)
        d_s   = s_mode(d_frame_c, mode)
        d_frame_c[label] = rmean(d_s, period_this)
        d_frame_c.reset_index(inplace=True, drop=True)
        d_frame_c[label].plot(ax=ax)
    # endfor
    # Plot volume
    v_data = [ 0 if j == 'n/a' else j for j in d_frame_c['v'] ]
    ax2 = ax.twinx()
    bc = volume_overlay(ax2, d_frame_c['o'], d_frame_c['c'], v_data, colorup='g', alpha=0.2, width=0.6)
    ax2.add_collection(bc)

    # Post-processing
    plt.grid()
    ax.xaxis.set_major_locator(ticker.MaxNLocator(6))
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(mydate))
    fig.autofmt_xdate()
    #fig.tight_layout()

    # Check if file_name was passed. If passed, save the plot to this file
    # else just plot the figure right now
    if file_name:
        if time_out:
            time.sleep(time_out)
        # endif
        plt.savefig(os.path.expanduser(file_name))
    else:
        if time_out:
            timer.start()
        # endif
        plt.show()
    # endif
# enddef

# For use by external server
def gen_candlestick_wrap(sym, res='1D', mode='c', period_list=[9, 14, 21], plot_period=40, plot_dir='~/outputs/'):
    if res not in res_tbl:
        return "Resolution should be one of {}".format(res_tbl.keys())
    # endif
    sym_name = scan_security_by_symbol(sym)
    j_data, sec_name = fetch_data(sym, res, sym_name=sym_name)
    if j_data is None:
        return sec_name
    # endif
    file_name = '{}/{}.png'.format(plot_dir, sym)
    gen_candlestick(j_data, period_list=period_list, title=sec_name, file_name=file_name, plot_period=plot_period)
    return file_name
# enddef

################################################################
# For EMA calculations
# Get mean generating f
def g_rmean_f(**kwargs):
    se_st = kwargs.get('type', 's')    # "s" or "e"
    if se_st == 's':
        return lambda s, t: pandas.rolling_mean(s, t)
    elif se_st == 'e':
        return lambda s, t: pandas.ewma(s, span=t, adjust=False)
    else:
        assert(False)
    # endif
# enddef

def s_mode(f_frame, mode='c'):
    m_list = ['o', 'c', 'h', 'l', 'hl2', 'hlc3', 'ohlc4']
    if not mode in m_list:
        print "mode should be one of {}".format(m_list)
        sys.exit(-1)
    # endif

    if mode == 'o':
        return f_frame['o']
    elif mode == 'c':
        return f_frame['c']
    elif mode == 'h':
        return f_frame['h']
    elif mode == 'l':
        return f_frame['l']
    elif mode == 'hl2':
        return (f_frame['h'] + f_frame['l'])/2.0
    elif mode == 'hlc3':
        return (f_frame['h'] + f_frame['l'] + f_frame['c'])/3.0
    elif mode == 'ohlc4':
        return (f_frame['o'] + f_frame['h'] + f_frame['l'] + f_frame['c'])/4.0
    else:
        assert(False)
    # endif
# enddef

#########################################################
# Main func
if __name__ == '__main__':
    # ignore warnings
    warnings.filterwarnings("ignore")
    send_mail = False

    prsr = argparse.ArgumentParser()
    prsr.add_argument("--sym",     help="symbol",                 type=str, default=None)
    prsr.add_argument("--res",     help="resolution",             type=str, default=None)
    prsr.add_argument("--pfile",   help="plot file",              type=str, default=None)
    prsr.add_argument("--nbars",   help="no of candles to print", type=int, default=40)
    prsr.add_argument("--stime",   help="Sleep time. Default=None", type=int, default=None)
    prsr.add_argument("--eauth",   help="email authentication",   type=str, default=None)
    args = prsr.parse_args()

    ### Symbol
    if args.__dict__["sym"] == None:
        print '--sym is required !!'
        sys.exit(-1)
    else:
        sym = args.__dict__["sym"]
    # endif
    ### Resolution
    if args.__dict__["res"] == None:
        print '--res is required !! It can be any of the following {}'.format(res_tbl.keys())
        sys.exit(-1)
    else:
        assert(args.__dict__["res"] in res_tbl.keys())
        res = args.__dict__["res"]
    # endif
    ### Candle stick chart file
    pfile = args.__dict__["pfile"]
    ### Auth info
    if args.__dict__["eauth"]:
        eargs = args.__dict__["eauth"].split(",")
        if len(eargs) != 2:
            print "--eauth should be in form username,password"
            sys.exit(-1)
        # endif
        send_mail = True
    # endif

    # get socket
    sock = g_sock()
    print "sock = {}".format(sock)

    sym_name = scan_security_by_symbol(sym)
    if pfile:
        print 'Plotting {} for resolution {} to {}. Using {} bars, {} sleep time'.format(sym_name, res, pfile, \
                args.__dict__["nbars"], args.__dict__["stime"])
    # endif
    while True:
        # Fetch data and generate plot file
        j_data, sec_name = fetch_data(sym, res, sym_name=sym_name)
        # Check for any error
        if j_data is None:
            print sec_name
            sys.exit(-1)
        # endif
        gen_candlestick(j_data, period_list=[9, 14, 21], title=sec_name, file_name=pfile, \
            plot_period=args.__dict__["nbars"], time_out=args.__dict__["stime"])
        if send_mail:
            if os.path.exists(pfile) and os.path.isfile(pfile):
                #print 'Sending email..'
                send_email(eargs[0], eargs[1], eargs[0], attachments=[pfile], subject='{} at {}'.format(sec_name, datetime.datetime.now()))
            # endif
        # endif
        if args.__dict__["stime"] == None:
            break
        # endif
    # endwhile
# enddef