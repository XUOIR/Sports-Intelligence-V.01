export async function api<T>(path:string,options:RequestInit={}):Promise<T>{
  const response=await fetch(`/api/data/${path}`,{...options,headers:{'Content-Type':'application/json',...options.headers},cache:'no-store'});
  if(response.status===401){window.location.replace('/login');throw Object.assign(new Error('Your session expired. Sign in again.'),{status:401});}
  const body=await response.json();
  if(!response.ok)throw Object.assign(new Error(body.detail||'Request failed'),{status:response.status});
  return body;
}
