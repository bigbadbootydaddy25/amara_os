import { PluginSearch } from '@/components/PluginSearch';

export const metadata = {
  title: 'AMARA Plugin Store',
  description: 'Discover and install plugins to extend your AMARA experience',
};

export default function PluginsPage() {
  return <PluginSearch />;
}
