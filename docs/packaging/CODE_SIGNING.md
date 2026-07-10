# Code signing (not done yet -- requires a real purchase)

`dist\SightSingingStudio.exe` and `installer-output\SightSingingStudioSetup.exe`
are currently **unsigned**. Windows SmartScreen will show an "Unknown
publisher" warning the first time anyone runs the installer or the app, and
many school IT departments block unsigned executables outright via policy.
This is the single biggest blocker to a real school deployment on the
distribution side.

This is not something that can be automated or downloaded as a tool -- it
requires a purchase and an identity-verification process with a Certificate
Authority. Here's what's actually involved:

## What you need to do

1. **Buy a code signing certificate** from a CA such as
   [DigiCert](https://www.digicert.com/signing/code-signing-certificates) or
   [Sectigo](https://sectigo.com/ssl-certificates-tls/code-signing). Expect:
   - **OV (Organization Validation)**: cheaper, still triggers SmartScreen
     warnings until the certificate builds up enough reputation ("SmartScreen
     reputation" accrues over time/downloads).
   - **EV (Extended Validation)**: pricier (roughly $300-500+/year as of this
     writing), but gets **immediate** SmartScreen trust with no warm-up
     period. This is the one actually worth buying for a product you're
     selling to schools.
   - Either way, expect to provide business registration documents, and for
     EV specifically, the private key is issued on a hardware token (USB) --
     it cannot be exported or stored as a normal file, which affects how you
     automate signing (see below).

2. **Sign the executables** once you have the certificate. With `signtool`
   (part of the Windows SDK):
   ```powershell
   signtool sign /tr http://timestamp.digicert.com /td sha256 /fd sha256 `
     /f "path\to\cert.pfx" /p "cert-password" `
     "dist\SightSingingStudio.exe"

   signtool sign /tr http://timestamp.digicert.com /td sha256 /fd sha256 `
     /f "path\to\cert.pfx" /p "cert-password" `
     "installer-output\SightSingingStudioSetup.exe"
   ```
   For an EV certificate on a hardware token, replace `/f ... /p ...` with
   the CA's signing tool/CSP for that token (each vendor's process differs
   slightly) -- there's no `.pfx` file to point at.

3. **Sign the installer, not just the app inside it.** Both need signing:
   the installer .exe itself, and the app .exe it installs.

## Once you have a certificate

Add a signing step to the build process (a `sign.ps1` calling `signtool` on
both artifacts) and run it after `pyinstaller sight_singing.spec` and after
compiling `sight_singing_installer.iss`, before distributing either file.
This repo intentionally does not include a signing step yet since there's no
certificate to sign with.
