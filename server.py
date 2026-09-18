from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json, sqlite3, os, mimetypes
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from cryptography.fernet import Fernet

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
DB_PATH = os.path.join(BASE_DIR, 'household.db')
KEY_PATH = os.path.join(BASE_DIR, '.bank_key')

if not os.path.exists(KEY_PATH):
    with open(KEY_PATH, 'wb') as f:
        f.write(Fernet.generate_key())
with open(KEY_PATH, 'rb') as f:
    fernet = Fernet(f.read())

def money(v):
    return float(Decimal(str(v)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    return conn

def init_db():
    conn = db()
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS households(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      currency TEXT NOT NULL DEFAULT 'EUR',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS members(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      household_id INTEGER NOT NULL REFERENCES households(id) ON DELETE CASCADE,
      name TEXT NOT NULL,
      email TEXT,
      color TEXT DEFAULT '#7C6CFF',
      active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS expenses(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      household_id INTEGER NOT NULL REFERENCES households(id) ON DELETE CASCADE,
      title TEXT NOT NULL,
      amount REAL NOT NULL,
      category TEXT NOT NULL,
      expense_date TEXT NOT NULL,
      due_date TEXT,
      payer_id INTEGER NOT NULL REFERENCES members(id),
      note TEXT,
      status TEXT NOT NULL DEFAULT 'open',
      recurring_id INTEGER,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS expense_splits(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      expense_id INTEGER NOT NULL REFERENCES expenses(id) ON DELETE CASCADE,
      member_id INTEGER NOT NULL REFERENCES members(id),
      share REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS recurring_expenses(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      household_id INTEGER NOT NULL REFERENCES households(id) ON DELETE CASCADE,
      title TEXT NOT NULL,
      amount REAL NOT NULL,
      category TEXT NOT NULL,
      payer_id INTEGER NOT NULL REFERENCES members(id),
      day_of_month INTEGER NOT NULL,
      note TEXT,
      active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS settlements(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      household_id INTEGER NOT NULL REFERENCES households(id) ON DELETE CASCADE,
      from_member_id INTEGER NOT NULL REFERENCES members(id),
      to_member_id INTEGER NOT NULL REFERENCES members(id),
      amount REAL NOT NULL,
      paid_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      note TEXT
    );
    CREATE TABLE IF NOT EXISTS settings(
      household_id INTEGER PRIMARY KEY REFERENCES households(id) ON DELETE CASCADE,
      owner_name TEXT,
      email TEXT,
      preferred_currency TEXT DEFAULT 'EUR',
      bank_name_enc BLOB,
      iban_enc BLOB,
      account_holder_enc BLOB,
      notifications INTEGER NOT NULL DEFAULT 1
    );
    ''')
    count = conn.execute('SELECT COUNT(*) c FROM households').fetchone()['c']
    if count == 0:
        conn.execute("INSERT INTO households(name,currency) VALUES('Lezama House','EUR')")
        hid = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        members = [('Marwan','marwan@example.com','#6C63FF'),('Alex','alex@example.com','#39A0FF'),('Sofia','sofia@example.com','#FF7A8A'),('Leo','leo@example.com','#26C6A3')]
        ids=[]
        for m in members:
            cur=conn.execute('INSERT INTO members(household_id,name,email,color) VALUES(?,?,?,?)',(hid,*m)); ids.append(cur.lastrowid)
        today=date.today()
        sample=[
            ('September Rent',1800,'Rent', today.replace(day=1).isoformat(), today.replace(day=5).isoformat(), ids[0], 'Monthly apartment rent', [450,450,450,450]),
            ('Groceries',142.60,'Groceries',(today-timedelta(days=4)).isoformat(),None,ids[2],'Weekly groceries',[35.65]*4),
            ('Internet',49.99,'Internet',(today-timedelta(days=7)).isoformat(),today.isoformat(),ids[1],'Fiber plan',[12.50,12.50,12.50,12.49]),
            ('Electricity',96.40,'Utilities',(today-timedelta(days=11)).isoformat(),(today-timedelta(days=2)).isoformat(),ids[3],'August electricity bill',[24.10]*4),
        ]
        for title,amt,cat,ed,dd,payer,note,shares in sample:
            cur=conn.execute('INSERT INTO expenses(household_id,title,amount,category,expense_date,due_date,payer_id,note) VALUES(?,?,?,?,?,?,?,?)',(hid,title,amt,cat,ed,dd,payer,note))
            eid=cur.lastrowid
            for mid,sh in zip(ids,shares):
                conn.execute('INSERT INTO expense_splits(expense_id,member_id,share) VALUES(?,?,?)',(eid,mid,sh))
        conn.execute('INSERT INTO recurring_expenses(household_id,title,amount,category,payer_id,day_of_month,note) VALUES(?,?,?,?,?,?,?)',(hid,'Rent',1800,'Rent',ids[0],1,'Paid on the first of each month'))
        conn.execute('INSERT INTO settings(household_id,owner_name,email,preferred_currency) VALUES(?,?,?,?)',(hid,'Marwan','marwan@example.com','EUR'))
    conn.commit(); conn.close()

def rows_to_dict(rows): return [dict(r) for r in rows]

def household_balance(conn,hid):
    members=rows_to_dict(conn.execute('SELECT * FROM members WHERE household_id=? AND active=1 ORDER BY id',(hid,)))
    bal={m['id']:0.0 for m in members}
    expenses=conn.execute('SELECT * FROM expenses WHERE household_id=?',(hid,)).fetchall()
    for e in expenses:
        bal[e['payer_id']] += e['amount']
        for s in conn.execute('SELECT * FROM expense_splits WHERE expense_id=?',(e['id'],)):
            bal[s['member_id']] -= s['share']
    for s in conn.execute('SELECT * FROM settlements WHERE household_id=?',(hid,)):
        bal[s['from_member_id']] += s['amount']
        bal[s['to_member_id']] -= s['amount']
    return members, {k:money(v) for k,v in bal.items()}

def optimal_settlements(members, balances):
    ids=[m['id'] for m in members]
    vals=[round(balances[i],2) for i in ids]
    eps=.005
    best_path=None
    memo={}
    def norm(v): return tuple(round(x,2) if abs(x)>eps else 0.0 for x in v)
    def dfs(v):
        nonlocal best_path
        state=norm(v)
        if state in memo: return memo[state]
        i=next((k for k,x in enumerate(state) if abs(x)>eps),None)
        if i is None: return (0,[])
        best=(10**9,[])
        for j in range(i+1,len(state)):
            if state[i]*state[j] >= 0: continue
            amt=min(abs(state[i]),abs(state[j]))
            nv=list(state)
            if state[i] < 0:
                tx=(ids[i],ids[j],money(amt))
                nv[i]+=amt; nv[j]-=amt
            else:
                tx=(ids[j],ids[i],money(amt))
                nv[i]-=amt; nv[j]+=amt
            cnt,path=dfs(nv)
            if 1+cnt < best[0]: best=(1+cnt,[tx]+path)
            if abs(state[i]+state[j]) < eps: break
        memo[state]=best
        return best
    _,path=dfs(vals)
    names={m['id']:m['name'] for m in members}
    return [{'from_id':a,'to_id':b,'from_name':names[a],'to_name':names[b],'amount':c} for a,b,c in path]

class Handler(SimpleHTTPRequestHandler):
    def translate_path(self,path):
        p=urlparse(path).path
        if p=='/': p='/index.html'
        return os.path.join(STATIC_DIR,p.lstrip('/'))
    def log_message(self,*args): pass
    def send_json(self,obj,status=200):
        data=json.dumps(obj,ensure_ascii=False).encode()
        self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
    def body(self):
        n=int(self.headers.get('Content-Length',0)); raw=self.rfile.read(n) if n else b'{}'
        return json.loads(raw or b'{}')
    def do_GET(self):
        u=urlparse(self.path); p=u.path; q=parse_qs(u.query)
        if not p.startswith('/api/'):
            return super().do_GET()
        conn=db()
        try:
            hid=int(q.get('household_id',['1'])[0])
            if p=='/api/bootstrap':
                households=rows_to_dict(conn.execute('SELECT * FROM households ORDER BY id'))
                members=rows_to_dict(conn.execute('SELECT * FROM members WHERE household_id=? ORDER BY active DESC,id',(hid,)))
                expenses=rows_to_dict(conn.execute('''SELECT e.*,m.name payer_name FROM expenses e JOIN members m ON m.id=e.payer_id WHERE e.household_id=? ORDER BY e.expense_date DESC,e.id DESC''',(hid,)))
                for e in expenses:
                    e['splits']=rows_to_dict(conn.execute('SELECT s.member_id,s.share,m.name FROM expense_splits s JOIN members m ON m.id=s.member_id WHERE s.expense_id=?',(e['id'],)))
                recurring=rows_to_dict(conn.execute('''SELECT r.*,m.name payer_name FROM recurring_expenses r JOIN members m ON m.id=r.payer_id WHERE r.household_id=? ORDER BY day_of_month''',(hid,)))
                settlements=rows_to_dict(conn.execute('''SELECT s.*,fm.name from_name,tm.name to_name FROM settlements s JOIN members fm ON fm.id=s.from_member_id JOIN members tm ON tm.id=s.to_member_id WHERE s.household_id=? ORDER BY paid_at DESC''',(hid,)))
                mem,bals=household_balance(conn,hid)
                plan=optimal_settlements(mem,bals)
                self.send_json({'households':households,'members':members,'expenses':expenses,'recurring':recurring,'settlements':settlements,'balances':bals,'settlement_plan':plan})
            elif p=='/api/settings':
                r=conn.execute('SELECT * FROM settings WHERE household_id=?',(hid,)).fetchone()
                if not r: return self.send_json({})
                d=dict(r)
                for k in ['bank_name_enc','iban_enc','account_holder_enc']:
                    out=k.replace('_enc','')
                    try: d[out]=fernet.decrypt(d[k]).decode() if d[k] else ''
                    except: d[out]=''
                    d.pop(k,None)
                self.send_json(d)
            else: self.send_json({'error':'Not found'},404)
        finally: conn.close()
    def do_POST(self):
        u=urlparse(self.path); p=u.path; data=self.body(); conn=db()
        try:
            if p=='/api/expenses':
                hid=int(data['household_id']); amount=money(data['amount'])
                cur=conn.execute('''INSERT INTO expenses(household_id,title,amount,category,expense_date,due_date,payer_id,note) VALUES(?,?,?,?,?,?,?,?)''',(hid,data['title'],amount,data['category'],data['expense_date'],data.get('due_date') or None,int(data['payer_id']),data.get('note','')))
                eid=cur.lastrowid
                splits=data.get('splits',[])
                if not splits:
                    mids=[r['id'] for r in conn.execute('SELECT id FROM members WHERE household_id=? AND active=1',(hid,))]
                    base=money(amount/len(mids)); shares=[base]*len(mids); shares[-1]=money(amount-sum(shares[:-1])); splits=[{'member_id':mid,'share':sh} for mid,sh in zip(mids,shares)]
                for s in splits: conn.execute('INSERT INTO expense_splits(expense_id,member_id,share) VALUES(?,?,?)',(eid,int(s['member_id']),money(s['share'])))
                conn.commit(); self.send_json({'ok':True,'id':eid},201)
            elif p=='/api/members':
                cur=conn.execute('INSERT INTO members(household_id,name,email,color) VALUES(?,?,?,?)',(int(data['household_id']),data['name'],data.get('email',''),data.get('color','#7C6CFF'))); conn.commit(); self.send_json({'ok':True,'id':cur.lastrowid},201)
            elif p=='/api/households':
                cur=conn.execute('INSERT INTO households(name,currency) VALUES(?,?)',(data['name'],data.get('currency','EUR'))); hid=cur.lastrowid
                conn.execute('INSERT INTO settings(household_id,preferred_currency) VALUES(?,?)',(hid,data.get('currency','EUR'))); conn.commit(); self.send_json({'ok':True,'id':hid},201)
            elif p=='/api/settlements':
                conn.execute('INSERT INTO settlements(household_id,from_member_id,to_member_id,amount,note) VALUES(?,?,?,?,?)',(int(data['household_id']),int(data['from_member_id']),int(data['to_member_id']),money(data['amount']),data.get('note','Settled through app'))); conn.commit(); self.send_json({'ok':True},201)
            elif p=='/api/recurring':
                cur=conn.execute('INSERT INTO recurring_expenses(household_id,title,amount,category,payer_id,day_of_month,note) VALUES(?,?,?,?,?,?,?)',(int(data['household_id']),data['title'],money(data['amount']),data['category'],int(data['payer_id']),int(data['day_of_month']),data.get('note','')));conn.commit();self.send_json({'ok':True,'id':cur.lastrowid},201)
            elif p=='/api/settings':
                hid=int(data['household_id'])
                enc=lambda s: fernet.encrypt((s or '').encode()) if s else None
                conn.execute('''INSERT INTO settings(household_id,owner_name,email,preferred_currency,bank_name_enc,iban_enc,account_holder_enc,notifications) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(household_id) DO UPDATE SET owner_name=excluded.owner_name,email=excluded.email,preferred_currency=excluded.preferred_currency,bank_name_enc=excluded.bank_name_enc,iban_enc=excluded.iban_enc,account_holder_enc=excluded.account_holder_enc,notifications=excluded.notifications''',(hid,data.get('owner_name',''),data.get('email',''),data.get('preferred_currency','EUR'),enc(data.get('bank_name','')),enc(data.get('iban','')),enc(data.get('account_holder','')),1 if data.get('notifications',True) else 0));conn.commit();self.send_json({'ok':True})
            else: self.send_json({'error':'Not found'},404)
        except Exception as e:
            conn.rollback(); self.send_json({'error':str(e)},400)
        finally: conn.close()

    def do_PUT(self):
        u=urlparse(self.path); p=u.path; data=self.body(); conn=db()
        try:
            if p.startswith('/api/expenses/'):
                eid=int(p.rsplit('/',1)[1]); amount=money(data['amount'])
                conn.execute("UPDATE expenses SET title=?,amount=?,category=?,expense_date=?,due_date=?,payer_id=?,note=? WHERE id=?",(data['title'],amount,data['category'],data['expense_date'],data.get('due_date') or None,int(data['payer_id']),data.get('note',''),eid))
                conn.execute('DELETE FROM expense_splits WHERE expense_id=?',(eid,))
                for sp in data.get('splits',[]):
                    conn.execute('INSERT INTO expense_splits(expense_id,member_id,share) VALUES(?,?,?)',(eid,int(sp['member_id']),money(sp['share'])))
                conn.commit(); self.send_json({'ok':True})
            else: self.send_json({'error':'Not found'},404)
        except Exception as e:
            conn.rollback(); self.send_json({'error':str(e)},400)
        finally: conn.close()

    def do_DELETE(self):
        u=urlparse(self.path); p=u.path; conn=db()
        try:
            if p.startswith('/api/expenses/'):
                eid=int(p.rsplit('/',1)[1]); conn.execute('DELETE FROM expenses WHERE id=?',(eid,)); conn.commit(); self.send_json({'ok':True})
            elif p.startswith('/api/members/'):
                mid=int(p.rsplit('/',1)[1]); conn.execute('UPDATE members SET active=0 WHERE id=?',(mid,)); conn.commit(); self.send_json({'ok':True})
            else:self.send_json({'error':'Not found'},404)
        finally: conn.close()

if __name__=='__main__':
    init_db()
    port=int(os.environ.get('PORT','8000'))
    print(f'HouseSplit running at http://127.0.0.1:{port}')
    ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
