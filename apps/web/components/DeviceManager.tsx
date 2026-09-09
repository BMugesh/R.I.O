'use client';

import React, { useEffect, useState } from 'react';
import { Laptop, Smartphone, Radio, CheckCircle, RefreshCw } from 'lucide-react';
import { Device } from '../../../packages/types';
import { getApiBaseUrl } from '../lib/api';

export const DeviceManager: React.FC = () => {
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchDevices = async () => {
    setLoading(true);
    try {
      const apiBase = getApiBaseUrl();
      const res = await fetch(`${apiBase}/api/v1/devices`);
      if (res.ok) {
        const data = await res.json();
        setDevices(data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDevices();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">Registered Devices</h2>
          <p className="text-xs text-slate-400">Hardware peripherals connected to R.I.O. Core</p>
        </div>
        <button
          onClick={fetchDevices}
          className="p-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-300 hover:text-white transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {devices.map((device) => (
          <div key={device.deviceId} className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-3 rounded-xl bg-cyan-500/10 text-cyan-400">
                  {device.type === 'laptop' || device.type === 'desktop' ? <Laptop className="w-5 h-5" /> : <Smartphone className="w-5 h-5" />}
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white">{device.name}</h3>
                  <span className="text-xs font-mono text-slate-400">{device.deviceId}</span>
                </div>
              </div>
              <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 text-xs font-medium">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                {device.status}
              </span>
            </div>

            <div>
              <span className="text-[11px] font-mono text-slate-500 uppercase tracking-wider">Capabilities</span>
              <div className="flex flex-wrap gap-1.5 mt-2">
                {device.capabilities.map((cap) => (
                  <span key={cap} className="px-2 py-0.5 rounded-lg bg-slate-950 border border-slate-800 text-[11px] font-mono text-slate-300">
                    {cap}
                  </span>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
