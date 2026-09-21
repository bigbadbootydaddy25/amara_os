import type { Metadata } from 'next';
import { LandExplorer } from '@/components/land/LandExplorer';

export const metadata: Metadata = {
  title: 'AMARA — Land Intelligence',
  description: 'Address search, power-line overlay, and soil/septic feasibility screening.',
};

export default function LandPage() {
  return (
    <div className="h-screen w-screen overflow-hidden">
      <LandExplorer />
    </div>
  );
}
