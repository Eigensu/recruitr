"use client";
import React, { useState, useRef } from "react";
import {
  IconSearch,
  IconMail,
  IconUpload,
  IconHelp,
  IconChevronDown,
  IconClock,
  IconBold,
  IconItalic,
  IconStrikethrough,
  IconLink,
  IconList,
  IconListNumbers,
} from "@tabler/icons-react";

export default function SettingsPage() {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const COUNTRY_CODES: Record<string, string> = {
    Australia: "au",
    "United States": "us",
    "United Kingdom": "gb",
    India: "in",
  };
  const [selectedCountry, setSelectedCountry] = useState("Australia");
  const countryCode = COUNTRY_CODES[selectedCountry] ?? "au";

  function handleFileChange(files: FileList | null) {
    if (!files || files.length === 0) return;
    // TODO: upload files[0] to Cloudinary / backend
    console.log("File selected:", files[0].name);
  }

  return (
    <div className="p-6 md:p-10 max-w-6xl mx-auto w-full animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <h1 className="text-3xl font-heading font-bold text-text-primary">Settings</h1>
        <div className="relative w-full sm:w-auto">
          <IconSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted w-5 h-5" />
          <input
            type="text"
            placeholder="Search"
            className="w-full sm:w-64 pl-10 pr-12 py-2 rounded-lg border border-border bg-surface text-text-primary focus:outline-none focus:ring-2 focus:ring-navy dark:focus:ring-yellow transition-shadow"
          />
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-text-muted bg-canvas px-1.5 py-0.5 rounded border border-border">
            ⌘K
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex space-x-1 border-b border-border overflow-x-auto scrollbar-none mb-8 pb-[1px]">
        {["My details", "Profile", "Team", "Notifications", "Integrations"].map((tab, i) => (
          <button
            key={tab}
            className={`px-4 py-2 text-sm font-medium whitespace-nowrap transition-colors ${
              i === 0
                ? "text-text-primary border-b-2 border-text-primary"
                : "text-text-secondary hover:text-text-primary hover:bg-surface-2 rounded-t-lg"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Main Section */}
      <div>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h2 className="text-lg font-bold text-text-primary">Personal info</h2>
            <p className="text-sm text-text-secondary mt-1">
              Update your photo and personal details here.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button className="px-4 py-2 text-sm font-medium rounded-lg border border-border text-text-primary bg-surface hover:bg-surface-2 transition-colors cursor-pointer">
              Cancel
            </button>
            <button className="px-4 py-2 text-sm font-medium rounded-lg bg-navy dark:bg-yellow dark:text-navy text-white hover:bg-navy-dark dark:hover:bg-yellow-dark transition-colors cursor-pointer">
              Save
            </button>
          </div>
        </div>

        <div className="divide-y divide-border border-y border-border">
          {/* Name Row */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 py-6 items-start md:items-center">
            <label htmlFor="firstName" className="text-sm font-medium text-text-primary">
              Name{" "}
              <span className="text-red-500 dark:text-yellow-dark" aria-hidden="true">
                *
              </span>
            </label>
            <div className="md:col-span-2 flex flex-col sm:flex-row gap-4 max-w-2xl">
              <label htmlFor="firstName" className="sr-only">
                First name
              </label>
              <input
                id="firstName"
                type="text"
                defaultValue="Olivia"
                className="w-full px-3 py-2 rounded-lg border border-border bg-surface text-text-primary focus:outline-none focus:ring-2 focus:ring-navy dark:focus:ring-yellow transition-shadow"
              />
              <label htmlFor="lastName" className="sr-only">
                Last name
              </label>
              <input
                id="lastName"
                type="text"
                defaultValue="Rhye"
                className="w-full px-3 py-2 rounded-lg border border-border bg-surface text-text-primary focus:outline-none focus:ring-2 focus:ring-navy dark:focus:ring-yellow transition-shadow"
              />
            </div>
          </div>

          {/* Email Row */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 py-6 items-start md:items-center">
            <label htmlFor="email" className="text-sm font-medium text-text-primary">
              Email address{" "}
              <span className="text-red-500 dark:text-yellow-dark" aria-hidden="true">
                *
              </span>
            </label>
            <div className="md:col-span-2">
              <div className="relative max-w-md">
                <IconMail className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted w-5 h-5" />
                <input
                  id="email"
                  type="email"
                  defaultValue="olivia@untitledui.com"
                  className="w-full pl-10 pr-3 py-2 rounded-lg border border-border bg-surface text-text-primary focus:outline-none focus:ring-2 focus:ring-navy dark:focus:ring-yellow transition-shadow"
                />
              </div>
            </div>
          </div>

          {/* Photo Row */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 py-6">
            <div>
              <label
                htmlFor="photoUpload"
                className="text-sm font-medium text-text-primary flex items-center gap-1.5"
              >
                Your photo{" "}
                <span className="text-red-500 dark:text-yellow-dark" aria-hidden="true">
                  *
                </span>
                <IconHelp className="w-4 h-4 text-text-muted" />
              </label>
              <p className="text-sm text-text-secondary mt-1">
                This will be displayed on your profile.
              </p>
            </div>
            <div className="md:col-span-2 flex flex-col sm:flex-row items-start sm:items-center gap-6">
              <div className="w-16 h-16 rounded-full overflow-hidden shrink-0 border border-border shadow-sm">
                <img
                  src="https://i.pravatar.cc/150?u=olivia"
                  alt="Avatar"
                  className="w-full h-full object-cover"
                />
              </div>
              <input
                id="photoUpload"
                ref={fileInputRef}
                type="file"
                accept="image/svg+xml,image/png,image/jpeg,image/gif"
                className="hidden"
                onChange={(e) => handleFileChange(e.target.files)}
              />
              <div
                className="flex-1 w-full max-w-md border-2 border-dashed border-border rounded-xl p-6 flex flex-col items-center justify-center text-center hover:bg-surface-2 transition-colors cursor-pointer group"
                onClick={() => fileInputRef.current?.click()}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    fileInputRef.current?.click();
                  }
                }}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  handleFileChange(e.dataTransfer.files);
                }}
                role="button"
                tabIndex={0}
                aria-label="Upload photo — click or drag and drop"
              >
                <div className="w-10 h-10 rounded-full bg-surface shadow-sm border border-border flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
                  <IconUpload className="w-5 h-5 text-text-secondary" />
                </div>
                <p className="text-sm text-text-secondary">
                  <span className="text-navy dark:text-yellow font-medium">Click to upload</span> or
                  drag and drop
                </p>
                <p className="text-xs text-text-muted mt-1">
                  SVG, PNG, JPG or GIF (max. 800x400px)
                </p>
              </div>
            </div>
          </div>

          {/* Role Row */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 py-6 items-start md:items-center">
            <label htmlFor="role" className="text-sm font-medium text-text-primary">
              Role
            </label>
            <div className="md:col-span-2 max-w-md">
              <input
                id="role"
                type="text"
                defaultValue="Recruiter"
                className="w-full px-3 py-2 rounded-lg border border-border bg-surface text-text-primary focus:outline-none focus:ring-2 focus:ring-navy dark:focus:ring-yellow transition-shadow"
              />
            </div>
          </div>

          {/* Country Row */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 py-6 items-start md:items-center">
            <label htmlFor="country" className="text-sm font-medium text-text-primary">
              Country
            </label>
            <div className="md:col-span-2 max-w-md">
              <div className="relative">
                <select
                  id="country"
                  value={selectedCountry}
                  onChange={(e) => setSelectedCountry(e.target.value)}
                  className="w-full pl-10 pr-10 py-2 rounded-lg border border-border bg-surface text-text-primary appearance-none focus:outline-none focus:ring-2 focus:ring-navy dark:focus:ring-yellow transition-shadow"
                >
                  {Object.keys(COUNTRY_CODES).map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
                <div className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 rounded-full overflow-hidden border border-border">
                  <img
                    src={`https://flagcdn.com/w20/${countryCode}.png`}
                    alt={selectedCountry}
                    className="w-full h-full object-cover"
                  />
                </div>
                <IconChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted w-4 h-4 pointer-events-none" />
              </div>
            </div>
          </div>

          {/* Timezone Row */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 py-6 items-start md:items-center">
            <label
              htmlFor="timezone"
              className="text-sm font-medium text-text-primary flex items-center gap-1.5"
            >
              Timezone <IconHelp className="w-4 h-4 text-text-muted" />
            </label>
            <div className="md:col-span-2 max-w-md">
              <div className="relative">
                <IconClock className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted w-5 h-5" />
                <select
                  id="timezone"
                  className="w-full pl-10 pr-10 py-2 rounded-lg border border-border bg-surface text-text-primary appearance-none focus:outline-none focus:ring-2 focus:ring-navy dark:focus:ring-yellow transition-shadow"
                >
                  <option>Pacific Standard Time (PST) UTC-08:00</option>
                  <option>Australian Eastern Standard Time (AEST)</option>
                  <option>Coordinated Universal Time (UTC)</option>
                </select>
                <IconChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted w-4 h-4 pointer-events-none" />
              </div>
            </div>
          </div>

          {/* Bio Row */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 py-6">
            <div>
              <label
                htmlFor="bio"
                className="text-sm font-medium text-text-primary flex items-center gap-1.5"
              >
                Bio{" "}
                <span className="text-red-500 dark:text-yellow-dark" aria-hidden="true">
                  *
                </span>
              </label>
              <p className="text-sm text-text-secondary mt-1">Write a short introduction.</p>
            </div>
            <div className="md:col-span-2 max-w-md">
              <div className="border border-border rounded-lg overflow-hidden bg-surface focus-within:ring-2 focus-within:ring-navy dark:focus-within:ring-yellow focus-within:border-transparent transition-shadow">
                <div className="border-b border-border bg-surface-2 px-3 py-2 flex items-center gap-1 overflow-x-auto scrollbar-none">
                  <button
                    type="button"
                    className="p-1.5 text-text-secondary hover:text-text-primary hover:bg-border rounded transition-colors cursor-pointer"
                  >
                    <IconBold className="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    className="p-1.5 text-text-secondary hover:text-text-primary hover:bg-border rounded transition-colors cursor-pointer"
                  >
                    <IconItalic className="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    className="p-1.5 text-text-secondary hover:text-text-primary hover:bg-border rounded transition-colors cursor-pointer"
                  >
                    <IconStrikethrough className="w-4 h-4" />
                  </button>
                  <div className="w-px h-4 bg-border mx-1 shrink-0" />
                  <button
                    type="button"
                    className="p-1.5 text-text-secondary hover:text-text-primary hover:bg-border rounded transition-colors cursor-pointer"
                  >
                    <IconLink className="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    className="p-1.5 text-text-secondary hover:text-text-primary hover:bg-border rounded transition-colors cursor-pointer"
                  >
                    <IconList className="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    className="p-1.5 text-text-secondary hover:text-text-primary hover:bg-border rounded transition-colors cursor-pointer"
                  >
                    <IconListNumbers className="w-4 h-4" />
                  </button>
                </div>
                <textarea
                  id="bio"
                  rows={4}
                  className="w-full p-3 bg-transparent text-text-primary focus:outline-none resize-y min-h-[100px]"
                  defaultValue="I'm a Technical Recruiter based in Melbourne, Australia. I specialise in hiring engineering, product, and design talent."
                ></textarea>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
