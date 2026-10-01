'use client';

import React, { useState, useEffect } from 'react';
import { ShortlistEntry, Role, fetchWithAuth } from '@/lib/api';

export default function EvidenceDeskPage() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [activeRole, setActiveRole] = useState<string>('');
  const [shortlist, setShortlist] = useState<ShortlistEntry[]>([]);
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    loadRoles();
  }, []);

  async function loadRoles() {
    try {
      const data = await fetchWithAuth<{ roles: Role[] }>('/roles');
      setRoles(data.roles || []);
      if (data.roles?.length) {
        setActiveRole(data.roles[0].id);
      }
    } catch (e) {
      console.warn('Could not load roles:', e);
    }
  }

  return (
    <div style={{ minHeight: '100vh', background: '#0a0d14', color: '#f8fafc', padding: '2rem' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 800 }}>RecruitRadar — The Evidence Desk</h1>
          <p style={{ color: '#94a3b8', fontSize: '0.9rem' }}>Deterministic, explainable candidate ranking grounded in verbatim resume evidence.</p>
        </div>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <span style={{ fontSize: '0.85rem', color: '#34d399', background: 'rgba(16, 185, 129, 0.12)', padding: '0.35rem 0.85rem', borderRadius: 9999 }}>
            ● Blind Mode Active (EEOC Compliant)
          </span>
          <select
            value={activeRole}
            onChange={(e) => setActiveRole(e.target.value)}
            style={{ background: '#161f32', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', padding: '0.45rem 0.85rem', borderRadius: 8 }}
          >
            {roles.map((r) => (
              <option key={r.id} value={r.id}>
                {r.title} (v{r.jd_version})
              </option>
            ))}
          </select>
        </div>
      </header>

      <div style={{ background: 'rgba(22, 31, 50, 0.7)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: 16, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)', background: 'rgba(10, 13, 20, 0.8)' }}>
              <th style={{ padding: '1rem' }}>Rank</th>
              <th style={{ padding: '1rem' }}>Candidate</th>
              <th style={{ padding: '1rem' }}>Fit Score</th>
              <th style={{ padding: '1rem' }}>Confidence</th>
              <th style={{ padding: '1rem' }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {shortlist.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ textAlign: 'center', padding: '3rem', color: '#64748b' }}>
                  Select an active role and execute the pipeline to generate evidence-backed scores.
                </td>
              </tr>
            ) : (
              shortlist.map((entry) => (
                <tr key={entry.candidate_id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                  <td style={{ padding: '1rem', fontWeight: 800 }}>#{entry.rank}</td>
                  <td style={{ padding: '1rem' }}>{entry.display_alias}</td>
                  <td style={{ padding: '1rem', fontWeight: 800, color: '#6366f1' }}>{entry.fit_score}/100</td>
                  <td style={{ padding: '1rem' }}>{entry.confidence_label}</td>
                  <td style={{ padding: '1rem' }}>
                    <span style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#34d399', padding: '0.2rem 0.6rem', borderRadius: 9999, fontSize: '0.75rem' }}>
                      MET
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
