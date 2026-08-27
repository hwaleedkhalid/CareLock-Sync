/** DoctorDashboard — theme-aware using ds-* tokens. */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Users, Activity, FileText, ChevronRight, Search, Calendar, Heart, Thermometer, Droplets, Clock } from 'lucide-react';
import { useAuth } from '../../../shared/context/AuthContext';

const MOCK_PATIENTS = [
  { id: 1, name: 'Ahmed Raza',    mrn: 'MRN-00129834', age: 45, gender: 'M', condition: 'Hypertension',    status: 'admitted',   ward: 'Cardiology'     },
  { id: 2, name: 'Fatima Khan',   mrn: 'MRN-00129102', age: 32, gender: 'F', condition: 'Diabetes Type 2', status: 'outpatient', ward: 'Endocrinology' },
  { id: 3, name: 'Usman Shahid',  mrn: 'MRN-00130051', age: 67, gender: 'M', condition: 'COPD',             status: 'admitted',   ward: 'Pulmonology'    },
  { id: 4, name: 'Sara Ahmed',    mrn: 'MRN-00128774', age: 28, gender: 'F', condition: 'Appendicitis',    status: 'discharged', ward: 'Surgery'        },
];
const VITALS = [
  { name: 'Ahmed Raza',   bp: '138/88', hr: 82, temp: '37.1°C', spo2: '97%', alert: true  },
  { name: 'Fatima Khan',  bp: '120/80', hr: 76, temp: '36.8°C', spo2: '99%', alert: false },
  { name: 'Usman Shahid', bp: '145/95', hr: 90, temp: '37.4°C', spo2: '93%', alert: true  },
];

const STATUS_CHIP: Record<string, { bg: string; color: string; border: string }> = {
  admitted:   { bg: 'rgba(59,130,246,0.18)',  color: '#60a5fa',  border: 'rgba(59,130,246,0.30)'  },
  outpatient: { bg: 'rgba(192,132,252,0.18)', color: '#c084fc',  border: 'rgba(192,132,252,0.30)' },
  discharged: { bg: 'var(--ds-table-head-bg)', color: 'var(--ds-text-muted)', border: 'var(--ds-table-border)' },
};

const ICON_BG: Record<string, string> = {
  blue: 'rgba(59,130,246,0.18)', green: 'rgba(16,185,129,0.18)', amber: 'rgba(245,158,11,0.18)',
};
const ICON_COLOR: Record<string, string> = { blue: '#60a5fa', green: '#34d399', amber: '#fbbf24' };
const ICON_GRAD: Record<string, string> = { blue: 'linear-gradient(135deg,rgba(59,130,246,0.18),rgba(59,130,246,0.04))', green: 'linear-gradient(135deg,rgba(16,185,129,0.18),rgba(16,185,129,0.04))', amber: 'linear-gradient(135deg,rgba(245,158,11,0.18),rgba(245,158,11,0.04))' };

const card = (extra?: React.CSSProperties): React.CSSProperties => ({ background: 'var(--ds-card-bg)', border: '1px solid var(--ds-card-border)', borderRadius: '1rem', boxShadow: 'var(--ds-card-shadow)', ...extra });

const DoctorDashboard: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const stats = { patients: 18, encounters: 4, pending: 2 };
  const filtered = MOCK_PATIENTS.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase()) || p.mrn.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.5rem', fontFamily: "'Inter',sans-serif" }}>
      {/* Header */}
      <div className="ds-animate">
        <h1 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--ds-text-primary)', margin: 0, letterSpacing: '-0.02em' }}>Good morning, {user?.display_name?.split(' ')[0] ?? 'Doctor'}</h1>
        <p style={{ fontSize: '0.8125rem', color: 'var(--ds-text-muted)', margin: '0.25rem 0 0' }}>Here's your patient overview for today</p>
      </div>

      {/* Quick stats */}
      <div className="ds-animate ds-animate-d1" style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: '1rem' }}>
        {[
          { label: 'My Patients',        value: stats.patients,  accent: 'blue',  icon: <Users    style={{ width: 18, height: 18 }} />, to: '/doctor/patients'   },
          { label: "Today's Encounters", value: stats.encounters, accent: 'green', icon: <Calendar style={{ width: 18, height: 18 }} />, to: '/doctor/encounters' },
          { label: 'Pending Notes',      value: stats.pending,   accent: 'amber', icon: <FileText style={{ width: 18, height: 18 }} />, to: '/doctor/patients'   },
        ].map(s => (
          <button key={s.label} onClick={() => navigate(s.to)} style={{ background: ICON_GRAD[s.accent], border: '1px solid var(--ds-card-border)', borderRadius: '1rem', padding: '1.25rem', cursor: 'pointer', textAlign: 'left', transition: 'border-color 0.25s,transform 0.2s', fontFamily: 'inherit' }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--ds-card-hover-border)'; (e.currentTarget as HTMLElement).style.transform = 'translateY(-2px)'; }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--ds-card-border)'; (e.currentTarget as HTMLElement).style.transform = 'translateY(0)'; }}>
            <div style={{ width: 40, height: 40, background: ICON_BG[s.accent], borderRadius: '0.75rem', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '0.875rem' }}>
              <span style={{ color: ICON_COLOR[s.accent], display: 'flex' }}>{s.icon}</span>
            </div>
            <div style={{ fontSize: '1.625rem', fontWeight: 800, color: 'var(--ds-text-primary)', letterSpacing: '-0.02em' }}>{s.value}</div>
            <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--ds-text-secondary)', marginTop: '0.25rem' }}>{s.label}</div>
          </button>
        ))}
      </div>

      {/* Main panels */}
      <div className="ds-animate ds-animate-d2" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        {/* Patients */}
        <div style={card({ overflow: 'hidden' })}>
          <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--ds-table-border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h2 style={{ margin: 0, fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Users style={{ width: 14, height: 14, color: '#60a5fa' }} />My Patients
            </h2>
            <button onClick={() => navigate('/doctor/patients')} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 600, color: 'var(--ds-text-link)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
              View all <ChevronRight style={{ width: 12, height: 12 }} />
            </button>
          </div>
          <div style={{ padding: '0.625rem 1rem', borderBottom: '1px solid var(--ds-table-border)' }}>
            <div style={{ position: 'relative' }}>
              <Search style={{ width: 12, height: 12, color: 'var(--ds-text-muted)', position: 'absolute', left: '0.625rem', top: '50%', transform: 'translateY(-50%)' }} />
              <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search patients…" style={{ width: '100%', paddingLeft: '1.75rem', paddingRight: '0.625rem', paddingTop: '0.375rem', paddingBottom: '0.375rem', background: 'var(--ds-surface)', border: '1px solid var(--ds-border)', borderRadius: '0.5rem', fontSize: '0.75rem', color: 'var(--ds-text-primary)', outline: 'none', boxSizing: 'border-box', fontFamily: 'inherit' }} />
            </div>
          </div>
          {filtered.map(p => (
            <div key={p.id} onClick={() => navigate('/doctor/patients')} className="ds-table-row" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.75rem 1.25rem', cursor: 'pointer' }}>
              <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'linear-gradient(135deg,#3b82f6,#6366f1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: '0.6875rem', fontWeight: 800, flexShrink: 0 }}>
                {p.name.split(' ').map(n => n[0]).join('')}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--ds-text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.name}</div>
                <div style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>{p.mrn} · {p.age}y {p.gender} · {p.condition}</div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexShrink: 0 }}>
                <span style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>{p.ward}</span>
                <span style={{ fontSize: '0.625rem', fontWeight: 700, padding: '0.2rem 0.5rem', borderRadius: '2rem', border: `1px solid ${STATUS_CHIP[p.status].border}`, background: STATUS_CHIP[p.status].bg, color: STATUS_CHIP[p.status].color, textTransform: 'capitalize' }}>{p.status}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Vitals */}
        <div style={card({ overflow: 'hidden' })}>
          <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--ds-table-border)' }}>
            <h2 style={{ margin: 0, fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Activity style={{ width: 14, height: 14, color: '#34d399' }} />Latest Vitals
            </h2>
          </div>
          {VITALS.map((v, i) => (
            <div key={i} className="ds-table-row" style={{ padding: '1rem 1.25rem', borderTop: i > 0 ? '1px solid var(--ds-table-border)' : undefined }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.625rem' }}>
                <span style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--ds-text-primary)' }}>{v.name}</span>
                {v.alert && <span style={{ fontSize: '0.625rem', fontWeight: 800, padding: '0.2rem 0.5rem', borderRadius: '2rem', background: 'var(--ds-status-error-bg)', color: 'var(--ds-status-error-text)', border: '1px solid rgba(239,68,68,0.30)' }}>Alert</span>}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: '0.5rem' }}>
                {[
                  { icon: <Heart style={{ width: 11, height: 11 }} />, label: 'BP', value: v.bp, alert: v.alert && parseInt(v.bp) > 130 },
                  { icon: <Activity style={{ width: 11, height: 11 }} />, label: 'HR', value: `${v.hr}bpm`, alert: v.hr > 85 },
                  { icon: <Thermometer style={{ width: 11, height: 11 }} />, label: 'Temp', value: v.temp, alert: false },
                  { icon: <Droplets style={{ width: 11, height: 11 }} />, label: 'SpO2', value: v.spo2, alert: v.spo2 < '97%' },
                ].map(m => (
                  <div key={m.label} style={{ borderRadius: '0.625rem', padding: '0.5rem', textAlign: 'center', background: m.alert ? 'var(--ds-status-error-bg)' : 'var(--ds-table-head-bg)', border: `1px solid ${m.alert ? 'rgba(239,68,68,0.30)' : 'var(--ds-table-border)'}` }}>
                    <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '0.2rem', color: m.alert ? 'var(--ds-status-error-text)' : 'var(--ds-text-muted)' }}>{m.icon}</div>
                    <div style={{ fontSize: '0.6875rem', fontWeight: 800, color: m.alert ? 'var(--ds-status-error-text)' : 'var(--ds-text-primary)' }}>{m.value}</div>
                    <div style={{ fontSize: '0.5625rem', color: 'var(--ds-text-muted)' }}>{m.label}</div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Schedule */}
      <div className="ds-animate ds-animate-d3" style={card({ padding: '1.25rem' })}>
        <h2 style={{ margin: '0 0 1rem', fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Clock style={{ width: 14, height: 14, color: 'var(--ds-text-muted)' }} />Today's Schedule
        </h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {[
            { time: '09:00', patient: 'Ahmed Raza',   type: 'Follow-up',    ward: 'Cardiology',  done: true  },
            { time: '10:30', patient: 'Fatima Khan',  type: 'Consultation', ward: 'OPD',         done: true  },
            { time: '14:00', patient: 'Usman Shahid', type: 'Ward Round',   ward: 'Pulmonology', done: false },
            { time: '16:00', patient: 'New Patient',  type: 'Admission',    ward: 'Emergency',   done: false },
          ].map((s, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '0.75rem 0.875rem', borderRadius: '0.75rem', background: s.done ? 'transparent' : 'var(--ds-table-head-bg)', border: `1px solid ${s.done ? 'transparent' : 'var(--ds-table-border)'}`, opacity: s.done ? 0.45 : 1 }}>
              <span style={{ fontSize: '0.75rem', fontFamily: 'monospace', fontWeight: 700, color: 'var(--ds-text-muted)', flexShrink: 0, width: '3rem' }}>{s.time}</span>
              <div style={{ flex: 1 }}>
                <span style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--ds-text-primary)' }}>{s.patient}</span>
                <span style={{ fontSize: '0.75rem', color: 'var(--ds-text-muted)', marginLeft: '0.5rem' }}>{s.type} · {s.ward}</span>
              </div>
              {s.done && <span style={{ fontSize: '0.75rem', color: 'var(--ds-text-muted)' }}>Done</span>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default DoctorDashboard;
