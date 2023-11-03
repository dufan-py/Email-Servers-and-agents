from __future__ import annotations

from argparse import ArgumentParser
from email.mime.text import MIMEText
from poplib import POP3
from smtplib import SMTP

import tomli

parser = ArgumentParser()
parser.add_argument('--email', '-e', type=str, required=True)
parser.add_argument('--password', '-p', type=str, required=True)
parser.add_argument('--smtp', '-s', type=str)
parser.add_argument('--pop', '-P', type=str)

args = parser.parse_args()

with open('data/config.toml', 'rb') as f:
    _config = tomli.load(f)
    _domain = args.email.split('@')[-1]
    SMTP_SERVER = args.smtp or _config['agent'][_domain]['smtp']
    POP_SERVER = args.pop or _config['agent'][_domain]['pop']

with open('data/fdns.toml', 'rb') as f:
    FDNS = tomli.load(f)


def fdns_query(domain: str, type_: str) -> str | None:
    domain = domain.rstrip('.') + '.'
    return FDNS[type_][domain]


def smtp():
    # 连接SMTP服务器
    conn = SMTP('localhost', int(fdns_query(SMTP_SERVER, 'P')))
    # 创建一个空列表来存储邮件的收件人地址
    to = []

    # 循环获取收件人地址，直到用户输入空行为止
    while True:
        _to = input('To: ')
        if _to == '':
            break
        to.append(_to)

    # 获取邮件主题和内容
    subject = input('Subject: ')
    content = input('Content: ')

    # 创建一个MIMEText对象，用于表示纯文本邮件
    msg = MIMEText(content, 'plain', 'utf-8')

    # 设置邮件主题
    msg['Subject'] = subject

    # 设置发件人地址
    msg['From'] = args.email
    # 使用SMTP连接发送邮件
    #print(msg.as_string())
    conn.sendmail(args.email, to, msg.as_string())
    # 关闭SMTP连接
    conn.quit()


def pop():
    conn = POP3('localhost', int(fdns_query(POP_SERVER, 'P')))
    print(conn.getwelcome())
    print(conn.user(args.email))
    print(conn.pass_(args.password))
    while True:
        try:
            cmd = input('[pop]>>> ')
            if cmd == 'stat':
                msg, bts = conn.stat()[0:2]
                print(f'{msg} messages ({bts} bytes)')
            elif cmd == 'list':
                print(f' {conn.list()[1]} ')
            elif cmd.startswith('retr '):
                msg = list(map(str, conn.retr(int(cmd[5:]))[1])) #列表第二个元素第6个字符
                print('\r\n'.join(msg))
            elif cmd.startswith('dele '):
                print(conn.dele(int(cmd[5:])))
            elif cmd == 'rset':
                print(conn.rset())
            elif cmd == 'noop':
                print(conn.noop())
            elif cmd == 'quit':
                print(conn.quit())
                break
            else:
                print('Invalid command')
        except KeyboardInterrupt:
            conn.rset()
            raise
        except Exception as e:
            print('-ERR!!')
            print(repr(e))


if __name__ == '__main__':
    while True:
        try:
            cmd = input('[smtp|pop|exit]>>> ')
            if cmd == 'smtp':
                smtp()
            elif cmd == 'pop':
                pop()
            elif cmd == 'exit':
                break
            else:
                print('Invalid command')
        except KeyboardInterrupt:
            break
        except Exception as e:
            print('-ERR!!')
            print(repr(e))
