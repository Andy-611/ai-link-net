/* Chat page — contacts sidebar + conversation area. */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";

import { cn, EASE_SMOOTH } from "@/lib/utils";
import { useAppStore } from "@/stores/app";
import { ContactList } from "@/components/chat/contact-list";
import { ChatArea } from "@/components/chat/chat-area";
import type { Contact } from "@/types";

export function ChatPage() {
  const navigate = useNavigate();
  const contacts = useAppStore((s) => s.contacts);
  const loadContacts = useAppStore((s) => s.loadContacts);
  const refreshOnlineStatus = useAppStore((s) => s.refreshOnlineStatus);
  const setActiveChatUid = useAppStore((s) => s.setActiveChatUid);

  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [showChat, setShowChat] = useState(false);
  const [contactsLoaded, setContactsLoaded] = useState(false);

  useEffect(() => {
    loadContacts().then(() => setContactsLoaded(true));
    refreshOnlineStatus();
    const interval = setInterval(refreshOnlineStatus, 30_000);
    return () => clearInterval(interval);
  }, [loadContacts, refreshOnlineStatus]);

  // #13: redirect to entities page when no contacts after initial load
  useEffect(() => {
    if (contactsLoaded && contacts.length === 0) {
      navigate("/entities");
    }
  }, [contactsLoaded, contacts.length, navigate]);

  const handleSelectContact = useCallback(
    (contact: Contact) => {
      setSelectedContact(contact);
      setActiveChatUid(contact.entity_uid);
      setShowChat(true);
    },
    [setActiveChatUid],
  );

  const handleBack = useCallback(() => {
    setShowChat(false);
    setActiveChatUid(null);
  }, [setActiveChatUid]);

  return (
    <div className="flex h-full min-h-0 w-full overflow-hidden">
      {/* Contact sidebar — hidden on mobile when chat is open */}
      <div
        className={cn(
          "w-full md:w-72 min-h-0 border-r border-border bg-sidebar flex flex-col shrink-0",
          showChat ? "hidden md:flex" : "flex",
        )}
      >
        <div className="px-4 h-14 flex items-center border-b border-sidebar-border shrink-0">
          <h1 className="font-heading text-sm font-semibold">Messages</h1>
        </div>
        <ContactList onSelect={handleSelectContact} />
      </div>

      {/* Chat area — full width on mobile, flex on desktop */}
      <div
        className={cn(
          "flex-1 min-h-0 min-w-0 flex flex-col overflow-hidden",
          showChat ? "flex" : "hidden md:flex",
        )}
      >
        {selectedContact ? (
          <ChatArea contact={selectedContact} onBack={handleBack} />
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground gap-4">
            {/* Animated network icon with layered glow */}
            <motion.div
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.6, ease: EASE_SMOOTH }}
              className="relative"
            >
              <div className="h-24 w-24 rounded-2xl bg-muted border border-border flex items-center justify-center relative overflow-hidden">
                <svg
                  className="h-12 w-12 text-muted-foreground/30"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1"
                  strokeLinecap="round"
                >
                  <circle cx="12" cy="12" r="3" />
                  <circle cx="4" cy="6" r="1.5" />
                  <circle cx="20" cy="6" r="1.5" />
                  <circle cx="4" cy="18" r="1.5" />
                  <circle cx="20" cy="18" r="1.5" />
                  <line x1="9.5" y1="10.5" x2="5.5" y2="7" />
                  <line x1="14.5" y1="10.5" x2="18.5" y2="7" />
                  <line x1="9.5" y1="13.5" x2="5.5" y2="17" />
                  <line x1="14.5" y1="13.5" x2="18.5" y2="17" />
                </svg>
              </div>
            </motion.div>
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2, duration: 0.4 }}
              className="text-center"
            >
              <p className="text-sm font-medium text-foreground/60">
                Select a contact
              </p>
              <p className="text-xs text-muted-foreground/40 mt-1">
                to start a conversation
              </p>
            </motion.div>
          </div>
        )}
      </div>
    </div>
  );
}
