import {create} from 'zustand';
export const useUI=create<{mobileOpen:boolean;setMobileOpen:(value:boolean)=>void}>((set)=>({mobileOpen:false,setMobileOpen:(mobileOpen)=>set({mobileOpen})}));
