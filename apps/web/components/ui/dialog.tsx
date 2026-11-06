'use client';
import * as Dialog from '@radix-ui/react-dialog';
import { X } from '@/components/icons';
export function Modal({open,onOpenChange,title,description,children,wide=false}:{open:boolean;onOpenChange:(open:boolean)=>void;title:string;description?:string;children:React.ReactNode;wide?:boolean}) {
 return <Dialog.Root open={open} onOpenChange={onOpenChange}><Dialog.Portal><Dialog.Overlay className="modal-overlay"/><Dialog.Content className={`modal ${wide?'modal-wide':''}`}><div className="modal-heading"><div><Dialog.Title>{title}</Dialog.Title><Dialog.Description>{description||'Changes are saved to your workspace.'}</Dialog.Description></div><Dialog.Close className="icon-button" aria-label="Close dialog"><X size={18}/></Dialog.Close></div>{children}</Dialog.Content></Dialog.Portal></Dialog.Root>;
}
