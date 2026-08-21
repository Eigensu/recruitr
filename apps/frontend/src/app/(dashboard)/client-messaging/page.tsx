"use client";

import { useEffect, useState } from "react";
import {
  getClientMessagesAdmin,
  createClientMessage,
  deleteClientMessage,
} from "@/lib/api/client-messaging-admin";
import { listClients, type Client } from "@/lib/api/clients";
import { useApiFetch } from "@/lib/api";
import { IconTrash, IconPlus } from "@tabler/icons-react";

interface MessageItem {
  _id: string;
  message_text: string;
  cta_url?: string;
  type: string;
  target_type: string;
  start_at: string;
  end_at: string;
}

export default function ClientMessagingPage() {
  const apiFetch = useApiFetch();
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);

  // Basic form state
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    message_text: "",
    target_type: "all" as "all" | "specific",
    target_client_ids: [] as string[],
    start_at: "",
    end_at: "",
    type: "announcement",
    cta_url: "",
  });

  const loadMessages = async () => {
    try {
      setLoading(true);
      const [res, clientsRes] = await Promise.all([
        getClientMessagesAdmin(apiFetch),
        listClients(apiFetch),
      ]);
      setMessages(res.items as MessageItem[]);
      setClients(clientsRes);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadMessages();

    const formatLocalDatetime = (date: Date) => {
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, "0");
      const day = String(date.getDate()).padStart(2, "0");
      const hours = String(date.getHours()).padStart(2, "0");
      const minutes = String(date.getMinutes()).padStart(2, "0");
      return `${year}-${month}-${day}T${hours}:${minutes}`;
    };

    setFormData((prev) => ({
      ...prev,
      start_at: formatLocalDatetime(new Date()),
      end_at: formatLocalDatetime(new Date(Date.now() + 86400000 * 7)),
    }));
  }, []);

  const handleDelete = async (id: string) => {
    if (confirm("Are you sure?")) {
      try {
        await deleteClientMessage(apiFetch, id);
        loadMessages();
      } catch (err) {
        console.error(err);
      }
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload = {
        message_text: formData.message_text,
        start_at: new Date(formData.start_at).toISOString(),
        end_at: new Date(formData.end_at).toISOString(),
        type: formData.type,
        target_type: formData.target_type as "all" | "specific",
        target_client_ids: formData.target_type === "specific" ? formData.target_client_ids : [],
        cta_url: formData.cta_url || undefined,
      };
      await createClientMessage(apiFetch, payload);
      setShowForm(false);

      loadMessages();
    } catch {
      alert("Failed to create message. Check date logic (end > start).");
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-2xl font-bold">Client Messaging</h1>
          <p className="text-sm text-gray-500">Manage banners displayed to clients.</p>
        </div>
        <button
          type="button"
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 px-4 py-2 bg-black text-white dark:bg-white dark:text-black rounded-md hover:opacity-90 transition-opacity text-sm font-medium"
        >
          <IconPlus className="size-4" /> {showForm ? "Cancel" : "New Message"}
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="mb-8 p-6 border rounded-lg bg-black/5 dark:bg-white/5 space-y-4"
        >
          <div>
            <label className="block text-sm font-medium mb-1">Message Text</label>
            <input
              required
              className="w-full p-2 border rounded"
              value={formData.message_text}
              onChange={(e) => setFormData({ ...formData, message_text: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Type</label>
              <select
                className="w-full p-2 border rounded"
                value={formData.type}
                onChange={(e) => setFormData({ ...formData, type: e.target.value })}
              >
                <option value="announcement">Announcement</option>
                <option value="seasonal">Seasonal</option>
                <option value="action">Action Needed</option>
                <option value="benchmark">Benchmark</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Target Type</label>
              <select
                className="w-full p-2 border rounded"
                value={formData.target_type}
                onChange={(e) =>
                  setFormData({ ...formData, target_type: e.target.value as "all" | "specific" })
                }
              >
                <option value="all">All Clients</option>
                <option value="specific">Specific Clients</option>
              </select>
            </div>
          </div>

          {formData.target_type === "specific" && (
            <div>
              <label className="block text-sm font-medium mb-2">Select Clients</label>
              <div className="max-h-48 overflow-y-auto border rounded p-2 space-y-2 bg-white dark:bg-zinc-900">
                {clients.map((c) => (
                  <label
                    key={c.id}
                    className="flex items-center gap-2 text-sm cursor-pointer hover:bg-gray-50 dark:hover:bg-zinc-800 p-1 rounded"
                  >
                    <input
                      type="checkbox"
                      checked={formData.target_client_ids.includes(c.id)}
                      onChange={(e) => {
                        const newIds = e.target.checked
                          ? [...formData.target_client_ids, c.id]
                          : formData.target_client_ids.filter((id) => id !== c.id);
                        setFormData({ ...formData, target_client_ids: newIds });
                      }}
                      className="rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-300 focus:ring focus:ring-3 focus:ring-blue-200/50"
                    />
                    <span>
                      {c.name} <span className="text-gray-400">({c.code})</span>
                    </span>
                  </label>
                ))}
                {clients.length === 0 && (
                  <p className="text-xs text-gray-500">No clients available.</p>
                )}
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Start At (Local Time)</label>
              <input
                required
                type="datetime-local"
                className="w-full p-2 border rounded"
                value={formData.start_at}
                onChange={(e) => setFormData({ ...formData, start_at: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">End At (Local Time)</label>
              <input
                required
                type="datetime-local"
                className="w-full p-2 border rounded"
                value={formData.end_at}
                onChange={(e) => setFormData({ ...formData, end_at: e.target.value })}
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">CTA URL (Optional)</label>
            <input
              className="w-full p-2 border rounded"
              value={formData.cta_url}
              onChange={(e) => setFormData({ ...formData, cta_url: e.target.value })}
            />
          </div>

          <button
            type="submit"
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors text-sm font-medium"
          >
            Create Message
          </button>
        </form>
      )}

      {loading ? (
        <p>Loading...</p>
      ) : (
        <div className="bg-white dark:bg-zinc-900 border rounded-lg overflow-hidden">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50 dark:bg-zinc-800/50">
              <tr>
                <th className="p-4 font-semibold">Message</th>
                <th className="p-4 font-semibold">Type</th>
                <th className="p-4 font-semibold">Target</th>
                <th className="p-4 font-semibold">Schedule</th>
                <th className="p-4 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {messages.length === 0 ? (
                <tr>
                  <td colSpan={5} className="p-4 text-center text-gray-500">
                    No messages found.
                  </td>
                </tr>
              ) : (
                messages.map((msg) => (
                  <tr
                    key={msg._id}
                    className="hover:bg-gray-50/50 dark:hover:bg-zinc-800/50 transition-colors"
                  >
                    <td className="p-4">
                      <p className="font-medium">{msg.message_text}</p>
                      {msg.cta_url && (
                        <a
                          href={msg.cta_url}
                          className="text-xs text-blue-500 underline"
                          target="_blank"
                          rel="noreferrer"
                        >
                          CTA Link
                        </a>
                      )}
                    </td>
                    <td className="p-4 capitalize">{msg.type}</td>
                    <td className="p-4 capitalize">{msg.target_type}</td>
                    <td className="p-4 text-xs text-gray-500 whitespace-nowrap">
                      {new Date(msg.start_at).toLocaleString()}
                      <br />
                      {new Date(msg.end_at).toLocaleString()}
                    </td>
                    <td className="p-4 text-right">
                      <button
                        type="button"
                        onClick={() => handleDelete(msg._id)}
                        className="p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 rounded"
                      >
                        <IconTrash className="size-4" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
