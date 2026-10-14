import {authenticated} from '@/lib/auth';
import {redirect} from 'next/navigation';
import Settings from '@/components/Settings';
export const dynamic='force-dynamic';
export default async function Page(){if(!await authenticated())redirect('/login');return <Settings/>;}
