import re
from datetime import timedelta
import pandas as pd
import plotly.express as px
import streamlit as st
st.set_page_config(page_title='CHS Complaint Dashboard', page_icon='⚡', layout='wide')
REQUIRED={'complaint_no':'COMPLAINT_NO','category':'COMPLAINT_TYPE','subcategory':'COMPLAINT_SUBTYPE','status_raw':'COMPLAINT_STATUS_AS_ON_SELECTED_DATE','created_date':'CREATE_DATE','created_time':'CREATED_TIME','closed_at':'CLOSING_DATE','sla_hours_raw':'SLA_TIME','sla_deadline':'ESTIMATE TIME OF CLOSURE','source':'SOURCE_OF_COMPLAINT','area_type':'AREA_TYPE','section':'SECTION','subdivision':'SUBDIVISION','division':'DIVISION','circle':'CIRCLE','zone':'ZONE','discom':'DISCOM','vendor':'SM VENDOR','time_taken_raw':'COMPLAIN_TIME_TAKEN_HHMM','escalated_level':'ESCALATED_LEVEL','escalated_role':'ESCALATED_ROLE','escalated_date':'ESCALATED_DATE','responsible_role':'USER_RESPONSIBLE_ROLE','closing_details':'CLOSING_DETAILS','reopen':'REOPEN_COMPLAINT','fault_id':'FAULT_ID'}
PII={'MOBILE_NO','CONSUMER_NAME','CUSTOMER_ACCOUNT_NO','COMPLAINT_DETAILS','AEMOBILE','JEMOBILE','FRT_MOBILE','OFFICER_REMARKS','REGISTERED_BY'}
ALIASES={'MUZZAFARPUR':'MUZAFFARPUR','BHGALPUR':'BHAGALPUR'}
VENDORS={'GENUS_GSB23':'Genus','INTELLISMART':'IntelliSmart','ADANI_NIT4':'Adani','NCC_NIT4':'NCC','RMS':'RMS','EDF':'EDF','SECURE_NIT24':'Secure','HIPRINT_NIT4':'Hiprint','GRAMPOWER':'Grampower'}
COLORS={'SUPPLY RELATED':'#F59E0B','SMART METER RELATED':'#EAB308','BILL RELATED':'#F43F5E','METER RELATED':'#A855F7','MISCELLANEOUS':'#0EA5E9','ROOF TOP SOLAR':'#22C55E'}
def nh(x): return re.sub(r'[_\s]+','',str(x).strip()).upper()
def clean(x,default='Unknown'):
    return default if pd.isna(x) or not str(x).strip() else re.sub(r'\s+',' ',str(x).replace('\t',' ')).strip()
def key(x):
    s=clean(x).upper(); return ALIASES.get(s,s)
def duration(x):
    if pd.isna(x): return float('nan')
    m=re.fullmatch(r'\s*(\d+)\s*:\s*(\d{1,2})(?::\d{1,2})?\s*',str(x))
    return int(m[1])+int(m[2])/60 if m else float('nan')
def load(file):
    raw=pd.read_csv(file,encoding='utf-8-sig',low_memory=False) if file.name.lower().endswith('.csv') else pd.read_excel(file)
    lookup={nh(c):c for c in raw.columns}; missing=[v for v in REQUIRED.values() if nh(v) not in lookup]
    if missing: raise ValueError('Missing required columns: '+', '.join(missing))
    raw=raw.drop(columns=[c for c in raw if nh(c) in {nh(x) for x in PII}]).dropna(axis=1,how='all')
    d=pd.DataFrame({k:raw[lookup[nh(v)]] for k,v in REQUIRED.items()})
    d['created_at']=pd.to_datetime(d.created_date,errors='coerce',dayfirst=True).dt.normalize()+pd.to_timedelta(pd.to_timedelta(d.created_time.astype(str).str.strip(),errors='coerce').dt.total_seconds().fillna(0),unit='s')
    d['closed_at']=pd.to_datetime(d.closed_at,errors='coerce',dayfirst=True); d['sla_hours']=d.sla_hours_raw.map(duration)
    d['sla_deadline']=pd.to_datetime(d.sla_deadline,errors='coerce',dayfirst=True).fillna(d.created_at+pd.to_timedelta(d.sla_hours,unit='h'))
    d['status_raw']=d.status_raw.map(lambda x:clean(x,'').upper())
    for c in ['category','subcategory','source','area_type','section','subdivision','division','circle','zone','discom','responsible_role']: d[c]=d[c].map(clean)
    d['area_type']=d.area_type.map(lambda x:'Unknown' if x=='Unknown' else x.title())
    for c in ['section','subdivision','division','circle','zone','discom']: d[c+'_key']=d[c].map(key)
    d['complaint_no']=d.complaint_no.map(lambda x:clean(x,'')); d['discom']=d.apply(lambda r:('NBPDCL' if r.complaint_no.upper().startswith('NB') else 'SBPDCL') if r.discom=='Unknown' else r.discom.upper(),axis=1)
    d['pending']=d.closed_at.isna()|d.status_raw.str.startswith('PENDING'); d['starred']=d.time_taken_raw.astype(str).str.contains(r'\*',na=False)
    d['elapsed_hours']=((d.closed_at.fillna(d.created_at)-d.created_at).dt.total_seconds()/3600).clip(lower=0)
    d['vendor']=d.vendor.map(lambda x:None if pd.isna(x) or not str(x).strip() else clean(x,'').upper())
    d['vendor_display']=d.vendor.map(lambda x:'Unspecified' if not x else VENDORS.get(x,re.sub(r'_(NIT|GSB).*?$','',x).title()))
    d['reopen']=d.reopen.astype(str).str.upper().eq('YES'); d['escalated']=d.escalated_level.map(lambda x:clean(x,'')!='')|d.escalated_role.map(lambda x:clean(x,'')!='')
    d['breach_a']=d.apply(lambda r:bool((r.created_at if r.pending else r.closed_at)>r.sla_deadline) if pd.notna(r.sla_deadline) and pd.notna(r.created_at) else False,axis=1)
    d['breach_b']=d.status_raw.str.endswith('BEYOND'); d['breach_c']=d.starred|((d.elapsed_hours>d.sla_hours)&d.sla_hours.notna())
    d['closed']=~d.pending; d['closed_within']=d.closed&~d.breach_a
    return d.reset_index(drop=True)
def main():
    st.markdown('<style>.stApp{background:#F8FAFC}.block-container{padding-top:1rem}</style>',unsafe_allow_html=True)
    st.title('⚡ CHS Complaint Dashboard'); st.caption('1912 Consumer Complaint & Redressal Monitoring · Data stays in your browser.')
    f=st.file_uploader('Upload daily complaint dump (.xlsx or .csv)',type=['xlsx','csv'])
    if f is None: st.info('Upload a complaint file to begin. Metrics are calculated only from uploaded data.'); return
    try: d=load(f)
    except Exception as e: st.error(str(e)); return
    latest=d.created_at.max().date(); st.caption(f'As of {latest:%d-%b-%Y} · {len(d):,} complaints loaded')
    with st.sidebar:
        st.header('Filters'); discom=st.selectbox('DISCOM',['Bihar (All)','SBPDCL','NBPDCL']); win=st.selectbox('Time window',['Latest Day','Last 7 Days','This Month','Custom range'])
        if win=='Custom range': start=st.date_input('From',latest-timedelta(days=6)); end=st.date_input('To',latest)
        else: end=latest; start=latest if win=='Latest Day' else latest-timedelta(days=6) if win=='Last 7 Days' else latest.replace(day=1)
        cats=st.multiselect('Category',['All']+sorted(d.category.unique()),default=['All']); src=st.multiselect('Source',sorted(d.source.unique())); areas=st.multiselect('Area type',sorted(d.area_type.unique())); basis=st.radio('SLA basis',['A','B','C'],format_func=lambda x:{'A':'A · Deadline','B':'B · System status','C':'C · Reported duration'}[x],horizontal=True)
    q=d.copy()
    if discom!='Bihar (All)': q=q[q.discom.str.upper()==discom]
    q=q[q.created_at.dt.date.between(start,end)]
    if cats and 'All' not in cats: q=q[q.category.isin(cats)]
    if src: q=q[q.source.isin(src)]
    if areas: q=q[q.area_type.isin(areas)]
    if q.empty: st.warning('No complaints in this selection.'); return
    n=len(q); closed=int(q.closed.sum()); pending=int(q.pending.sum()); breach=q['breach_'+basis.lower()]
    c=st.columns(6); c[0].metric('Disposal rate',f'{closed/n:.1%}',f'{closed:,} of {n:,} closed'); c[1].metric('Latest day',f"{int((q.created_at.dt.date==latest).sum()):,}",latest.strftime('%d-%b-%Y')); c[2].metric('Complaints',f'{n:,}'); c[3].metric('Pending',f'{pending:,}',f'{int((q.pending&breach).sum()):,} beyond SLA'); c[4].metric('Closed within SLA',f'{q.closed_within.sum()/n:.1%}',f'{q.closed_within.sum():,} of {n:,}'); c[5].metric('Median / P90 close hours',f"{q.loc[q.closed,'elapsed_hours'].median():.1f} / {q.loc[q.closed,'elapsed_hours'].quantile(.9):.1f}" if closed else 'n/a')
    st.subheader("Today's things to act on"); insights=[]
    if pending: insights.append(f'🔴 {pending} complaints pending; {int((q.pending&breach).sum())} beyond SLA under basis {basis}.')
    z=q.assign(_b=breach.values).groupby('subcategory').agg(volume=('complaint_no','size'),breached=('_b','sum')); z=z[z.volume>=5]
    if len(z):
        z['rate']=z.breached/z.volume; w=z.sort_values('rate',ascending=False).iloc[0]; insights.append(f"🟠 Highest subcategory breach: {z.sort_values('rate',ascending=False).index[0]} — {w.breached:.0f} of {w.volume} ({w.rate:.0%}), basis {basis}.")
    if abs(q.breach_a.mean()-q.breach_b.mean())>.2: insights.append(f"🟠 SLA bases A and B differ by {abs(q.breach_a.mean()-q.breach_b.mean()):.1%} ({q.breach_a.mean():.1%} vs {q.breach_b.mean():.1%}).")
    premature=q.closing_details.fillna('').str.contains(r'work in progress|awaiting|forwarded|consult|will check',case=False,regex=True)
    if premature.sum(): insights.append(f'🟠 {int(premature.sum())} closure remarks indicate pending work; review divisions.')
    for x in insights[:8]: st.write(x)
    if not insights: st.success('No action rule triggered for this selection.')
    st.subheader('Status reconciliation'); cols=st.columns(3)
    for col,label,name in zip(cols,['A · Deadline','B · System status','C · Reported duration'],['breach_a','breach_b','breach_c']): col.metric(label,f'{q[name].sum():,} ({q[name].mean():.1%})')
    st.caption(f"Rows disagreeing across SLA definitions: {(q[['breach_a','breach_b','breach_c']].nunique(axis=1)>1).sum():,}")
    left,right=st.columns([1.3,1])
    with left:
        st.subheader('30-day daily trend'); days=pd.date_range(end=latest,periods=30); t=q.assign(day=q.created_at.dt.normalize()).groupby(['day','category']).size().rename('Complaints').reset_index(); t=t[t.day.isin(days)]; st.plotly_chart(px.bar(t,x='day',y='Complaints',color='category',color_discrete_map=COLORS),use_container_width=True)
    with right:
        st.subheader('Category summary'); t=q.groupby('category').agg(New=('complaint_no','size'),Disposed=('closed','sum'),SLA_hours=('sla_hours','median'),Median_close_h=('elapsed_hours','median')).reset_index(); t['Disposed %']=(100*t.Disposed/t.New).round(1); st.dataframe(t,hide_index=True,use_container_width=True)
    st.subheader('Geography'); level=st.selectbox('Rank by',['circle','division','subdivision','section']); g=q.groupby(level).agg(Complaints=('complaint_no','size'),Disposed=('closed','sum'),Pending=('pending','sum'),Breached=('breach_a','sum')).sort_values('Complaints',ascending=False).head(20).reset_index(); g['Disposal %']=(100*g.Disposed/g.Complaints).round(1); st.dataframe(g,hide_index=True,use_container_width=True)
    st.subheader('Vendor performance · all vendor-tagged complaints'); v=q[q.vendor.notna()].groupby('vendor_display').agg(Total=('complaint_no','size'),Closed=('closed','sum'),Pending=('pending','sum'),Breached=('breach_a','sum')).sort_values('Total',ascending=False).reset_index()
    if v.empty: st.info('No vendor-tagged complaints in this selection.')
    else: v['Resolution %']=(100*v.Closed/v.Total).round(1); v['Beyond %']=(100*v.Breached/v.Total).round(1); st.dataframe(v,hide_index=True,use_container_width=True)
    st.subheader('Channel × category'); heat=q.pivot_table(index='source',columns='category',values='complaint_no',aggfunc='count',fill_value=0); st.plotly_chart(px.imshow(heat,text_auto=True,aspect='auto',color_continuous_scale='Oranges'),use_container_width=True)
    st.subheader('Data health'); fields=['complaint_no','category','subcategory','created_at','sla_hours','discom','source','area_type','division']; bl=pd.DataFrame({'Field':fields,'Blank %':[100*q[x].isna().mean() for x in fields]}); dup=int(q.complaint_no.duplicated().sum()); disagree=int((q[['breach_a','breach_b','breach_c']].nunique(axis=1)>1).sum()); score=max(0,100-int(35*dup/max(n,1)*100)-int(35*disagree/max(n,1)*100)-int(30*bl['Blank %'].mean()))
    a,b,c=st.columns(3); a.metric('Rows',f'{n:,}'); b.metric('Duplicate IDs',f'{dup:,}'); c.metric('Health score',f'{score}/100'); st.dataframe(bl,hide_index=True,use_container_width=True); st.caption(f"Starred time values: {q.starred.sum():,} · Date range: {q.created_at.min():%d-%b-%Y} to {q.created_at.max():%d-%b-%Y}")
    with st.expander('Executive daily report matrices'):
        for dc in ['NBPDCL','SBPDCL']:
            st.markdown(f'**{dc}**'); rows=[]
            for cat,x in q[q.discom.str.upper()==dc].groupby('category'):
                top=x.groupby('division').size().sort_values(ascending=False).head(5); rows.append({'Category':cat,'Top divisions':', '.join(f'{k} ({v})' for k,v in top.items()),'Ranking subtotal':int(top.sum()),'Category total':len(x),'Top-5 share':f'{top.sum()/len(x):.1%}'})
            st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
    # PII and complaint identifiers are omitted from this export.
    export=q.drop(columns=['complaint_no'],errors='ignore').to_csv(index=False).encode('utf-8-sig'); st.download_button('Download filtered data (CSV)',export,'chs_filtered.csv','text/csv')
    st.caption('PII columns are dropped during parsing. Data is processed in this Streamlit session and is not persisted by this app.')
if __name__=='__main__': main()
