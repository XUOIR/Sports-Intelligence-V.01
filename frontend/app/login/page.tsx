import {redirect} from 'next/navigation';
import {authenticated} from '@/lib/auth';
import Login from '@/components/Login';
export const dynamic='force-dynamic';
export default async function Page(){if(await authenticated())redirect('/');return <Login/>;}
